import json
import logging
import sys
import asyncio
import os
import configparser
import tempfile
import argparse
import datetime
import base58
import re

# Set this flag to true if running this script in an AWS VM or a lambda. False if in a Virtualbox VM.
AWS_ENV=True

if AWS_ENV:
    import aioboto3

from indy import ledger, did, wallet, pool
from indy.error import ErrorCode, IndyError


WALLET_KEY="tempSecret123" # Security is not really a concern, due to the transient nature of the lambda

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Uncomment the following to write logs to STDOUT
#
#stdoutHandler = logging.StreamHandler(sys.stdout)
#stdoutHandler.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#stdoutHandler.setFormatter(formatter)
#logger.addHandler(stdoutHandler)

async def writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp):
    if AWS_ENV:
           # Write an item to the trust_anchor_registration table in DynamoDB
            async with aioboto3.resource('dynamodb', region_name='us-west-2', endpoint_url="https://dynamodb.us-west-2.amazonaws.com") as dynamo_resource:
                table = dynamo_resource.Table('trust_anchor_registration')
                await table.put_item(
                    Item={
                        'did': entry['DID'],
                        'timestamp': isotimestamp,
                        'sourceEmail': entry['sourceEmail'],
                        'sourceIP': entry['sourceIP'],
                        'verkey': entry['verkey'],
                        'status': status,
                        'reason': reason
                    }
                )

async def addNYMs(future, pool_name, pool_genesis_txn_path, steward_seed, NYMs):
   # A dict to hold the results keyed on DID
   result = {
       "statusCode": 200
   }

   # Create ledger config from genesis txn file
   pool_config = json.dumps({"genesis_txn": str(pool_genesis_txn_path)})
   await pool.set_protocol_version(2)
   try:
      await pool.create_pool_ledger_config(pool_name, pool_config)
   except IndyError as err:
      if (err.error_code == ErrorCode.PoolLedgerConfigAlreadyExistsError):
         logger.warning("Pool %s already exists. Skipping create.", pool_name)
      else:
         raise

   # Open pool ledger
   logger.debug("Before open pool ledger %s.", pool_name)
   pool_handle = await pool.open_pool_ledger(pool_name, None)
   logger.debug("After open pool ledger %s.", pool_name)

   # Open Wallet and Get Wallet Handle
   logger.debug("Before create steward_wallet")
   wallet_name = pool_name + '_wallet'
   wallet_config = json.dumps({"id": wallet_name})
   wallet_credentials = json.dumps({"key": WALLET_KEY})
   try:
      await wallet.create_wallet(wallet_config, wallet_credentials)
   except IndyError as err:
      if (err.error_code == ErrorCode.WalletAlreadyExistsError):
         logger.warning("Wallet %s already exists. Skipping create.", pool_name)
      else:
         logger.debug("Unknown error during create_wallet")
         raise
   logger.debug("After create steward_wallet")
   steward_wallet_handle = await wallet.open_wallet(wallet_config, wallet_credentials)

   # Create steward DID from seed
   logger.debug("Before create and store did")
   steward_did_info = {'seed': steward_seed}
   (steward_did, steward_verkey) = await did.create_and_store_my_did(steward_wallet_handle, json.dumps(steward_did_info))
   logger.debug("After create and store did")

   # Prepare and send NYM transactions
   isotimestamp = datetime.datetime.now().isoformat()
   for entry in NYMs:
      status = "Pending"
      statusCode = 200
      reason = "Check if DID already exists."
      logger.debug("Check if did >%s< is an emptry string" % entry["DID"])
      if (len(entry["DID"]) == 0):
         break

      # Log that a check for did on STN is in progress. Logging this
      # status/reason may be useful in determining where interation with the STN
      # may be a problem (timeouts).
      logger.debug("Before write trust anchor registration log")
      await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
      logger.debug("After write trust anchor registration log")

      # Does the DID we are assigning Trust Anchor role exist on the ledger?
      logger.debug("Before build_get_nym_request")
      get_nym_txn_req = await ledger.build_get_nym_request(steward_did, entry["DID"])
      logger.debug("After build_get_nym_request")
      logger.debug("Before submit_request")
      get_nym_txn_resp = await ledger.submit_request(pool_handle, get_nym_txn_req)
      logger.debug("After submit_request")
      logger.debug("submit_request JSON response >%s<", get_nym_txn_resp)
      get_nym_txn_resp = json.loads(get_nym_txn_resp)

      # Create identity owner if it does not yet exist
      if (get_nym_txn_resp['result']['data'] == None):
        reason = "DID does not exist. Creating Trust Anchor identity."
        # Log that a check for did on STN is in progress. Logging this
        # status/reason may be useful in determining where interation with the STN
        # may be a problem (timeouts).
        logger.debug("Before write trust anchor registration log")
        await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
        logger.debug("After write trust anchor registration log")

        logger.debug("DID %s does not exist on the ledger. Will create identity owner with role %s.", entry["DID"], entry["role"])
        logger.debug("Before build_nym_request")
        nym_txn_req = await ledger.build_nym_request(steward_did, entry["DID"], entry["verkey"], entry["name"], entry["role"])
        logger.debug("After build_nym_request")
        logger.debug("Before sign_and_submit_request")
        await ledger.sign_and_submit_request(pool_handle, steward_wallet_handle, steward_did, nym_txn_req)
        logger.debug("After sign_and_submit_request")
        logger.debug("Before sleep 3 seconds")
        await asyncio.sleep(3)
        logger.debug("After sleep 3 seconds")

        reason = "Trust Anchor identity written to the ledger. Confirming DID exists on the ledger."
        # Log that a check for did on STN is in progress. Logging this
        # status/reason may be useful in determining where interation with the STN
        # may be a problem (timeouts).
        logger.debug("Before write trust anchor registration log")
        await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
        logger.debug("After write trust anchor registration log")

        # Make sure the identity was written to the ledger with the correct role
        logger.debug("Make sure DID was written to the ledger with a TRUST_ANCHOR role")
        logger.debug("Before build_get_nym_request")
        get_nym_txn_req = await ledger.build_get_nym_request(steward_did, entry["DID"])
        logger.debug("After build_get_nym_request")
        logger.debug("Before submit_request")
        get_nym_txn_resp = await ledger.submit_request(pool_handle, get_nym_txn_req)
        logger.debug("After submit_request")
        logger.debug("submit_request JSON response >%s<", get_nym_txn_resp)
        get_nym_txn_resp = json.loads(get_nym_txn_resp)
        if (get_nym_txn_resp['result']['data'] != None):
          get_nym_txn_resp = json.loads(get_nym_txn_resp['result']['data'])
          # TODO: figure out how to map "TRUST_ANCHOR" to the numeric "101"
          #       without hardcoding it.
          if (get_nym_txn_resp['role'] != "101"):
            # TODO: Give a more accurate reason why the write to the ledger failed.
            status = "Error"
            statusCode = 404
            reason = "Failed to write NYM identified by %s to the ledger with role %s. NYM exists, but with the wrong role. Role ID is %s" % (entry["DID"], entry["role"], get_nym_txn_resp['role'])
            logger.error(reason)
          else:
            status = "Success"
            statusCode = 200
            reason = "Successfully wrote NYM identified by %s to the ledger with role %s" % (entry["DID"], entry["role"])
            logger.debug(reason)
        else:
          # TODO: Give a more accurate reason why the write to the ledger failed.
          status = "Error"
          statusCode = 500
          reason = "Attempted to get NYM identified by %s from the ledger to verify role %s was given. Did not find the NYM on the ledger." % (entry["DID"], entry["role"])
          logger.error(reason)
      else:
        # TODO: DID already exists on the ledger. A Steward cannot modify an
        #       existing identity.
        status = "Error"
        statusCode = 409
        reason = "NYM %s already exists on the ledger. Stewards cannot change the role of an existing identity owner." % entry["DID"]
        logger.error(reason)
      await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)

      # Add status and reason for the status for each DID to the result
      result[entry["DID"]] = {
        'status': status,
        'statusCode': statusCode,
        'reason': reason
      }

      # Possible status codes: 200, 400, 500. From less severe 200 to most severe 500.
      # Return the overall status using the most severe status code.
      if statusCode > result['statusCode']:
        logger.debug("Status code >%d< is greater than result.statusCode >%d<", statusCode, result['statusCode'])
        result['statusCode'] = statusCode

   # Close wallets and pool
   logger.debug("Before close_wallet")
   await wallet.close_wallet(steward_wallet_handle)
   logger.debug("After close_wallet")
   logger.debug("Before close_pool_ledger")
   await pool.close_pool_ledger(pool_handle)
   logger.debug("After close_pool_ledger")

   logger.debug("Before set future result")
   future.set_result(result)
   logger.debug("After set future result")

def isb58ofLength(value, length):
    try:
      if len(base58.b58decode(value)) != length:
          logging.debug("%s base58 decoded is not the required length of %d bytes." % (value, length))
          return False
    except Exception as e:
        logging.exception("Failed to decode %s" % value)
        return False

    return True

def isValidDID(did):
    return isb58ofLength(did, 16)

def isValidFullVerkey(did, verkey):
    logger.debug("Validating full verkey %s with DID %s" % (verkey, did))
    if isb58ofLength(verkey, 32):
        decodedValue = base58.b58decode(verkey)
        logger.debug("Full verkey %s is the following 32 byte base58 encoded string: %s" % (verkey, decodedValue))
        decodedDIDValue = base58.b58decode(did)
        logger.debug("Full verkey %s is the following 32 byte base58 encoded string: %s" % (verkey, decodedValue))
        if decodedValue[0:16] == decodedDIDValue:
            logger.debug("The first 16 bytes of %s are the DID %s" % (decodedValue, decodedDIDValue))
            return True
        else:
            logger.debug("The first 16 bytes of %s are NOT the DID %s" % (decodedValue, decodedDIDValue))
    else:
        logger.debug("Full verkey %s is not a 32 byte base58 encoded string." % verkey)

    return False

def isValidAbbreviatedVerkey(verkey):
    # Are we validating an abbreviated verkey?
    if len(verkey) > 0 and verkey[0] == '~':
        # Abbreviated verkey
        return isb58ofLength(verkey[1:], 16)
    return False

def validateVerkey(did, verkey):
    if len(verkey) > 1:
        if verkey[0] == '~':
           if not isValidAbbreviatedVerkey(verkey):
               return "Abbreviated verkey %s must be a 16 byte base58 encoded string." % verkey
        else:
           if not isValidFullVerkey(did, verkey):
               return "Full verkey %s must be a 32 byte base58 encoded string where the DID %s is the first 16 bytes of the base58 decoded value." % (verkey, did)
    else:
        return "A verkey must be either a 16 byte base58 encoded string that begins with a tilde (a.k.a. abbreviated verkey), or a 32 byte base58 encoded string where the DID is first 16 bytes of the base58 decoded value."

def isValidEmail(email):
    if len(email) > 7:
        if re.match("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email) != None:
            return True
    return False

def validateNym(nym):
    # Validate entry
    #
    # Must contain DID, verkey, and sourceEmail. All other fields are added by
    # the lambda.
    errors = []
    if 'did' in nym:
        # Validate DID
        if not isValidDID(nym['did']):
            errors.append("DID %s must be a 16 byte base58 encoded string." % nym['did'])
    else:
        # When a request comes from API Gateway, this is unreachable code
        errors.append("A DID is required to create an identity on the ledger. Please provide a DID even if you provide a full (non-abbreviated) verkey.")

    if 'verkey' in nym:
        did = nym['did'] if 'did' in nym else None
        verkey = nym['verkey']
        # Validate verkey
        error = validateVerkey(did, verkey)
        if error:
            errors.append(error)
    else:
        # When a request comes from API Gateway, this is unreachable code
        errors.append("An abbreviated or full verkey is required to create an identity on the ledger.")

    if 'sourceEmail' in nym:
        # Validate email
        if not isValidEmail(nym['sourceEmail']):
            errors.append("Invalid email address")
    else:
        # When a request comes from API Gateway, this is unreachable code
        errors.append("An email address is required.")

    return errors

def trustAnchorNym(request, event):
    return {
        "DID": request['did'],
        "verkey": request['verkey'],
        "role": "TRUST_ANCHOR",
        "name": request['name'] if 'name' in request else " ",
        "sourceIP": event['requestContext']['identity']['sourceIp'],
        "sourceEmail": request['sourceEmail']
    }

def addErrors(did, errorsDict, errors):
    currentErrors = []

    # Do errors already exists keyed on did?
    if did in errorsDict:
        currentErrors = errorsDict[did]

    currentErrors.extend(errors)
    errorsDict[did] = currentErrors

    return errorsDict


def my_handler(event, context):
    # Local file system access, child processes, and similar artifacts may not
    # extend beyond the lifetime of the request, and any persistent state should
    # be stored in Amazon S3, Amazon DynamoDB, or another Internet-available
    # storage service. Lambda functions can include libraries, even native ones.
    # Each Lambda function receives 500MB of non-persistent disk space in its
    # own /tmp directory.

    logging.debug("In my_handler")
    responseCode = 200

    os.environ['HOME'] = tempfile.gettempdir()
    os.environ['RUST_LOG'] = 'trace'

    lambdaTaskRoot = os.environ['LAMBDA_TASK_ROOT']
    stewardSeed = os.environ['STEWARD_SEED']

    ## TODO: Lock the handler down to just POST requests?
    #if event['httpMethod'] != 'POST':
    #    # Return unsupported method error/exception

    nyms = []
    # TODO: Change the default for 'name' from " " to None once
    #       ledger.build_nym_request accepts None
    logging.debug("Event body >%s<" % event['body'])
    body = json.loads(event['body'])

    # Validate and build nyms from request body; setting name and sourceIP for
    # each nym.
    # TODO: Currently a non-empty 'name' is required. Set the default to None
    #       once ledger.build_nym_request accepts None for the NYM 'name/alias'
    # NOTE: errors is a dict keyed on the DID. This Lambda is fronted by AWS
    #       API Gateway with JSON Schema validation that ensures we will never
    #       reach this point without a DID for each NYM in the request body.
    errors = {}
    if 'batch' in body:
        logging.debug("Processing batch request...")
        for nym in body['batch']:
            did = nym['did']
            tmp_errors = validateNym(nym)
            if len(tmp_errors) == 0:
                nyms.append(trustAnchorNym(nym, event))
            else:
                errors = addErrors(did, errors, tmp_errors)
    else:
        logging.debug("Processing single (non-batch) request...")
        did = body['did']
        tmp_errors = validateNym(body)
        if len(tmp_errors) == 0:
            nyms.append(trustAnchorNym(body, event))
        else:
            errors = addErrors(did, errors, tmp_errors)

    # Check if errors is an empty dict
    if bool(errors) == False:
        logging.debug("No errors found in request...")
        # Get the steward seed and pool genesis file
        config = configparser.ConfigParser()
        try:
            configFile = os.path.join(lambdaTaskRoot, "nym.ini")
            config.read_file(open(configFile))
            #stewardSeed = config['steward']['Seed']
            genesisFile = os.path.join(lambdaTaskRoot, config['pool']['GenesisFile'])
        except FileNotFoundError as exc:
            raise Exception("Service configuration error. Configuration file {} not found".format(str(configFile)))
        except KeyError as exc:
            raise Exception("Service configuration error. Key {} not found.".format(str(exc)))

        poolName = genesisFile.split("_")[-2]

        logging.debug("Get asyncio event loop...")
        loop = asyncio.get_event_loop()
        # Pass the 'future' handle to addNYMs to allow addNYMs to set the
        # future's 'result'.
        logging.debug("Get future handle...")
        future = asyncio.Future()
        logging.debug("Call addNYMs...")
        asyncio.ensure_future(addNYMs(future, poolName, genesisFile, stewardSeed, nyms))
        logging.debug("Wait for future to complete...")
        loop.run_until_complete(future)
        logging.debug("Future is complete...")

        responseBody = future.result()
    else:
        logging.debug("Errors found in request...")
        # Return validation errors. Validation errors are keyed on DID. Just add
        # a statusCode of 400 and set responseBody to the errors dict.
        errors['statusCode'] = 400
        responseBody = errors

    responseCode = responseBody['statusCode']

    # The output from a Lambda proxy integration must be of the following JSON
    # object. The 'body' property must be a JSON string. For base64-encoded
    # payload, you must also set the 'isBase64Encoded' property to 'true'.
    response = {
        'statusCode': responseCode,
        'headers': {
            'Access-Control-Allow-Origin':'*'
        },
        'body': json.dumps(responseBody)
    }
    logging.debug("response: %s" % json.dumps(response))
    return response


# --------- Main -----------
def main():
  # TODO: make DID and verkey optional if a --csv is given.
  #       The csv file would take the form: "<DID>,<verkey>\n"
  parser = argparse.ArgumentParser()
  parser.add_argument('genesisFile', action="store")
  parser.add_argument('DID', action="store")
  parser.add_argument('verkey', action="store")
  parser.add_argument('stewardSeed', action="store")
  parser.add_argument('--role', action="store", dest="role", default=None,
      choices=["STEWARD", "TRUSTEE", "TRUST_ANCHOR"],
      help="Aassumed to be an Identity Owner if not given")
  parser.add_argument('--name', action="store", dest="name", default=None,
      help="A name/alias of the NYM")
  parser.add_argument('--source-ip', action="store", dest="sourceIP",
      default='128.0.0.1',
      help="The source IP address of the client invoking the AWS Lambda function.")
  parser.add_argument('--source-email', action="store", dest="sourceEmail",
      default='email@example.com', help="The Trust Anchor's email address.")
  args = parser.parse_args()

  # TODO: Add the logic to either add a single record or many from a CSV file.
  nyms = []

  # Validate and build nyms from request body; setting name and sourceIP for
  # each nym.
  # TODO: Currently a non-empty 'name' is required. Set the default to None
  #       once ledger.build_nym_request accepts None for the NYM 'name/alias'
  errors = {}

  # Mock a body from the client
  body = {
      "did": args.DID,
      "verkey": args.verkey,
      "name": args.name,
      "sourceEmail": args.sourceEmail
  }

  # Mock an event from the AWS API Gateway
  event = {
      "requestContext": {
          "identity": {
              "sourceIp": "127.0.0.1"
          }
      }
  }

  tmp_errors = validateNym(body)
  if len(tmp_errors) == 0:
      nyms.append(trustAnchorNym(body, event))
  else:
      errors = addErrors(args.DID, errors, tmp_errors)

  if bool(errors) == False:
      poolName = args.genesisFile.split("_")[-2]

      loop = asyncio.get_event_loop()
      # Pass the 'future' handle to addNYMs to allow addNYMs to set the future's
      # 'result'.
      future = asyncio.Future()
      asyncio.ensure_future(addNYMs(future, poolName, args.genesisFile,
        args.stewardSeed, nyms))
      loop.run_until_complete(future)
      loop.close()

      responseBody = future.result()
  else:
      # Return validation errors
      errors['statusCode'] = 400
      responseBody = errors

  responseCode = responseBody['statusCode']

  # The output from a Lambda proxy integration must be
  # of the following JSON object. The 'headers' property
  # is for custom response headers in addition to standard
  # ones. The 'body' property  must be a JSON string. For
  # base64-encoded payload, you must also set the 'isBase64Encoded'
  # property to 'true'.
  response = {
      'statusCode': responseCode,
      'headers': {
          'Access-Control-Allow-Origin':'*'
      },
      'body': json.dumps(responseBody)
  }
  logging.debug("response: %s" % json.dumps(response))
  print("%s" % json.dumps(response))

  if responseCode != 200:
     sys.exit(1)
  else:
     sys.exit(0)


if __name__ == "__main__":
        main()
