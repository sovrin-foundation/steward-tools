import json
import logging
import sys
import asyncio
import os
import configparser
import tempfile
import argparse
import datetime
import platform
from ctypes import cdll

import base58
import re

# Set this flag to true if running this script in an AWS VM or a lambda. False if in a Virtualbox VM.
AWS_ENV = True

if AWS_ENV:
  import aioboto3

from indy import ledger, did, wallet, pool, payment
from indy.error import ErrorCode, IndyError

PAYMENT_LIBRARY = 'libsovtoken'
PAYMENT_METHOD = 'sov'
PAYMENT_PREFIX = 'pay:sov:'

WALLET_KEY = "tempSecret123"  # Security is not really a concern, due to the transient nature of the lambda
DEFAULT_TOKENS_AMOUNT = 100000

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Uncomment the following to write logs to STDOUT
#
# stdoutHandler = logging.StreamHandler(sys.stdout)
# stdoutHandler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# stdoutHandler.setFormatter(formatter)
# logger.addHandler(stdoutHandler)

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

async def setup(pool_name, pool_genesis_txn_path, steward_seed):
  # Create ledger config from genesis txn file
  pool_config = json.dumps({"genesis_txn": str(pool_genesis_txn_path)})
  await pool.set_protocol_version(2)
  try:
    await pool.create_pool_ledger_config(pool_name, pool_config)
  except IndyError as err:
    if err.error_code == ErrorCode.PoolLedgerConfigAlreadyExistsError:
      logger.warning("Pool %s already exists. Skipping create.", pool_name)
    else:
      raise

  # Open pool ledger
  logger.debug("Before open pool ledger %s.", pool_name)
  pool_handle = await pool.open_pool_ledger(pool_name, None)
  logger.debug("After open pool ledger %s.", pool_name)

  # Open Wallet and Get Wallet Handle
  logger.debug("Before create steward_wallet")
  wallet_config = json.dumps({"id": pool_name + '_wallet'})
  wallet_credentials = json.dumps({"key": WALLET_KEY})
  try:
    await wallet.create_wallet(wallet_config, wallet_credentials)
  except IndyError as err:
    if (err.error_code == ErrorCode.WalletAlreadyExistsError):
      logger.warning("Wallet %s already exists. Skipping create.", wallet_config)
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

  return pool_handle, steward_wallet_handle, steward_did

async def teardown(pool_name, pool_handle, steward_wallet_handle):
  # Close wallets and pool
  logger.debug("Before close_wallet")
  await wallet.close_wallet(steward_wallet_handle)
  logger.debug("After close_wallet")
  logger.debug("Before close_pool_ledger")
  await pool.close_pool_ledger(pool_handle)
  logger.debug("After close_pool_ledger")

  # Delete wallet
  logger.debug("Before delete_wallet")
  wallet_config = json.dumps({"id": pool_name + '_wallet'})
  wallet_credentials = json.dumps({"key": WALLET_KEY})
  await wallet.delete_wallet(wallet_config, wallet_credentials)
  logger.debug("After delete_wallet")

async def addNYMs(future, pool_name, pool_genesis_txn_path, steward_seed, source_payment_address_seed, NYMs):
  # A dict to hold the results keyed on DID
  result = {
    "statusCode": 200
  }

  pool_handle, steward_wallet_handle, steward_did = await setup(pool_name, pool_genesis_txn_path, steward_seed)

  # Prepare and send NYM transactions
  isotimestamp = datetime.datetime.now().isoformat()
  for entry in NYMs:
    status = "Pending"
    statusCode = 200
    reason = "Check if DID already exists."
    logger.debug("Check if did >%s< is an emptry string" % entry["DID"])
    if (len(entry["DID"]) == 0):
      break

    try:
      # Log that a check for did on STN is in progress. Logging this
      # status/reason may be useful in determining where interaсtion with the STN
      # may be a problem (timeouts).
      logger.debug("Before write trust anchor registration log")
      await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
      logger.debug("After write trust anchor registration log")

      # Verify DID we are assigning Trust Anchor role doesn't exist on the ledger
      await verifyTargetNymNotExist(pool_handle, entry['DID'])

      reason = "DID does not exist. Creating Trust Anchor identity is allowed."
      # Log that a check for did on STN is in done.
      logger.debug("Before write trust anchor registration log")
      await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
      logger.debug("After write trust anchor registration log")

      if entry.get('targetPaymentAddress'):
        reason = "Check if Payment Address already contains tokens."

        # Log that a check for target payment address on STN is in progress.
        logger.debug("Before write trust anchor registration log")
        await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
        logger.debug("After write trust anchor registration log")

        loadPaymentLibrary()

        # Verify target Payment Address we are transferring tokens doesn't contain them yet
        await validateTargetPaymentAddress(pool_handle, steward_wallet_handle, steward_did,
                                           entry.get('targetPaymentAddress'))

        reason = "Payment Address does not contain tokens. Transferring tokens is allowed."
        # Log that a check for target payment address on STN is in done.
        logger.debug("Before write trust anchor registration log")
        await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
        logger.debug("After write trust anchor registration log")

        reason = "Check if Source Payment Address contains enough tokens for transferring."

        # Log that a check for source payment address on STN is in progress.
        logger.debug("Before write trust anchor registration log")
        await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
        logger.debug("After write trust anchor registration log")

        # Verify source Payment Address contains enough tokens
        source_payment_address = await createPaymentAddess(steward_wallet_handle, source_payment_address_seed)
        await validateSourcePaymentAddress(pool_handle, steward_wallet_handle, steward_did,
                                           source_payment_address, entry.get('tokensAmount'))

        reason = "Source Payment Address contains enough tokens. Transferring is allowed."
        # Log that a check for source payment address on STN is in done.
        logger.debug("Before write trust anchor registration log")
        await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
        logger.debug("After write trust anchor registration log")

      reason = "Creating Trust Anchor identity"
      # Log that a creation for did on STN is in progress.
      logger.debug("Before write trust anchor registration log")
      await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
      logger.debug("After write trust anchor registration log")

      logger.debug("DID %s does not exist on the ledger. Will create identity owner with role %s.", entry["DID"],
                   entry["role"])
      logger.debug("Before build_nym_request")
      nym_txn_req = await ledger.build_nym_request(steward_did, entry["DID"], entry["verkey"], entry["name"],
                                                   entry["role"])
      logger.debug("After build_nym_request")
      logger.debug("Before sign_and_submit_request")
      await ledger.sign_and_submit_request(pool_handle, steward_wallet_handle, steward_did, nym_txn_req)
      logger.debug("After sign_and_submit_request")
      logger.debug("Before sleep 3 seconds")
      await asyncio.sleep(3)
      logger.debug("After sleep 3 seconds")

      reason = "Trust Anchor identity written to the ledger. Confirming DID exists on the ledger."
      # Log that a check for did on STN is in progress.
      logger.debug("Before write trust anchor registration log")
      await writeTrustAnchorRegistrationLog(entry, status, reason, isotimestamp)
      logger.debug("After write trust anchor registration log")

      # Make sure the identity was written to the ledger with the correct role
      logger.debug("Make sure DID was written to the ledger with a TRUST_ANCHOR role")
      await verifyNymIsWritten(pool_handle, entry["DID"], entry["role"])

      status = "Success"
      statusCode = 200
      reason = "Successfully wrote NYM identified by %s to the ledger with role %s" % (
        entry["DID"], entry["role"])
      logger.debug(reason)

      # Transfer tokens to DID specified payment the address
      if entry.get('targetPaymentAddress'):
        status = "Pending"
        reason_inner = "Transfer tokens to payment address."

        logger.debug("Before write token transferring log")
        await writeTrustAnchorRegistrationLog(entry, status, reason_inner, isotimestamp)
        logger.debug("After write token transferring log")

        target_payment_address = entry['targetPaymentAddress']
        target_tokens_amount = entry.get('tokensAmount')

        await transferTokens(pool_handle, steward_wallet_handle, steward_did, source_payment_address,
                             target_payment_address, target_tokens_amount)

        status = "Success"
        reason_inner = "Successfully transferred %s tokens to %s payment address" % (
          target_tokens_amount, target_payment_address)
        logger.debug(reason_inner)

        logger.debug("Before write token transferring log")
        await writeTrustAnchorRegistrationLog(entry, status, reason_inner, isotimestamp)
        logger.debug("After write token transferring log")

        reason += '\n' + reason_inner
    except Exception as err:
      status = "Error"
      statusCode = err.status_code
      reason = str(err)
      logger.error(err)

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

  await teardown(pool_name, pool_handle, steward_wallet_handle)

  logger.debug("Before set future result")
  future.set_result(result)
  logger.debug("After set future result")


async def getNym(pool_handle, DID):
  logger.debug("Before build_get_nym_request")
  get_nym_txn_req = await ledger.build_get_nym_request(None, DID)
  logger.debug("After build_get_nym_request")

  logger.debug("Before submit_request")
  get_nym_txn_resp = await ledger.submit_request(pool_handle, get_nym_txn_req)
  logger.debug("After submit_request")

  logger.debug("submit_request JSON response >%s<", get_nym_txn_resp)
  get_nym_txn_resp = json.loads(get_nym_txn_resp)

  return get_nym_txn_resp

async def verifyTargetNymNotExist(pool_handle, DID):
  get_nym_txn_resp = await getNym(pool_handle, DID)

  if get_nym_txn_resp['result']['data']:
    err = Exception(
      "NYM %s already exists on the ledger. Stewards cannot change the role of an existing identity owner." % DID)
    err.status_code = 409
    raise err

async def verifyNymIsWritten(pool_handle, DID, role):
  get_nym_txn_resp = await getNym(pool_handle, DID)

  if not get_nym_txn_resp['result']['data']:
    # TODO: Give a more accurate reason why the write to the ledger failed.
    reason = "Attempted to get NYM identified by %s from the ledger to verify DID was applied. Did not find the NYM on the ledger." % (
      DID)
    logger.error(reason)
    err = Exception(reason)
    err.status_code = 500
    raise err

  get_nym_txn_resp = json.loads(get_nym_txn_resp['result']['data'])
  # TODO: figure out how to map "TRUST_ANCHOR" to the numeric "101"
  #       without hardcoding it.
  if get_nym_txn_resp['role'] != "101":
    # TODO: Give a more accurate reason why the write to the ledger failed.
    reason = "Failed to write NYM identified by %s to the ledger with role %s. NYM exists, but with the wrong role. Role ID is %s" % (
      DID, role, get_nym_txn_resp['role'])
    logger.error(reason)
    err = Exception(reason)
    err.status_code = 404
    raise err

async def getTokenSources(pool_handle, wallet_handle, steward_did, payment_address):
  logger.debug("Before build_get_payment_sources_request")
  get_payment_sources_req, payment_method = \
    await payment.build_get_payment_sources_request(wallet_handle, steward_did, payment_address)
  logger.debug("After build_get_payment_sources_request")

  logger.debug("Before submit_request")
  get_payment_sources_resp = await ledger.submit_request(pool_handle, get_payment_sources_req)
  logger.debug("After submit_request")
  logger.debug("submit_request JSON response >%s<", get_payment_sources_resp)

  logger.debug("Before parse_get_payment_sources_response")
  get_payment_sources_resp = await payment.parse_get_payment_sources_response(payment_method,
                                                                              get_payment_sources_resp)
  logger.debug("After get_payment_sources_resp")
  logger.debug("parse_get_payment_sources_response Sources JSON >%s<", get_payment_sources_resp)

  payment_sources = json.loads(get_payment_sources_resp)
  return payment_sources

def getSufficientTokenSources(token_sources, target_tokens_amount):
  sources_amount = 0
  sources = []

  for source in token_sources:
    sources_amount += source['amount']
    sources.append(source['source'])
    if sources_amount >= target_tokens_amount:
      break

  remaining_tokens_amount = sources_amount - target_tokens_amount

  return sources, remaining_tokens_amount

async def createPaymentAddess(wallet_handle, address_seed):
  logger.debug("Before create and store source payment address")
  payment_address_config = {'seed': address_seed}
  source_payment_address = await payment.create_payment_address(wallet_handle, PAYMENT_METHOD,
                                                                json.dumps(payment_address_config))
  logger.debug("After create and store source payment address")
  return source_payment_address

async def transferTokens(pool_handle, wallet_handle, steward_did, source_payment_address, target_payment_address,
                         target_tokens_amount):
  logger.debug("Before getting all token sources")
  token_sources = await getTokenSources(pool_handle, wallet_handle, steward_did, source_payment_address)
  logger.debug("After getting all token sources")

  target_tokens_amount = target_tokens_amount or DEFAULT_TOKENS_AMOUNT
  logger.debug("Tokens amount to transfer >%s<", target_tokens_amount)

  logger.debug("Before getting necessary token sources")
  token_sources, remaining_tokens_amount = getSufficientTokenSources(token_sources, target_tokens_amount)
  logger.debug("After getting necessary token sources")

  logger.debug("Token sources %s", token_sources)
  logger.debug("Remaining tokens amount %s", remaining_tokens_amount)

  logger.debug("Before build_payment_req")

  inputs = token_sources
  outputs = [
    {"recipient": target_payment_address, "amount": target_tokens_amount},
    {"recipient": source_payment_address, "amount": remaining_tokens_amount}
  ]
  payment_req, payment_method = await payment.build_payment_req(wallet_handle, steward_did,
                                                                json.dumps(inputs), json.dumps(outputs), None)
  logger.debug("After build_payment_req")

  logger.debug("Before sign_and_submit_request")
  payment_resp = await ledger.sign_and_submit_request(pool_handle, wallet_handle, steward_did, payment_req)
  logger.debug("After sign_and_submit_request")
  logger.debug("sign_and_submit_request JSON response >%s<", payment_resp)

  logger.debug("Before parse_payment_response")
  receipts = await payment.parse_payment_response(payment_method, payment_resp)
  logger.debug("After get_payment_sources_resp")
  logger.debug("parse_payment_response Receipts JSON >%s<", receipts)

  receipts = json.loads(receipts)

  if len(receipts) != 2:
    err = Exception(
      "Failed to transfer %s tokens to %s payment address. Wrong number of receipts has been created: %s." % (
        target_tokens_amount, target_payment_address, receipts))
    err.status_code = 500
    raise err

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
        return "Full verkey %s must be a 32 byte base58 encoded string where the DID %s is the first 16 bytes of the base58 decoded value." % (
          verkey, did)
  else:
    return "A verkey must be either a 16 byte base58 encoded string that begins with a tilde (a.k.a. abbreviated verkey), or a 32 byte base58 encoded string where the DID is first 16 bytes of the base58 decoded value."

def isValidEmail(email):
  if len(email) > 7:
    if re.match("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email) != None:
      return True
  return False

def isPaymentAddress(payment_address: str):
  logger.debug("Validating payment address %s" % payment_address)
  payment_address = payment_address[8:] if payment_address.startswith(PAYMENT_PREFIX) else payment_address

  if not isb58ofLength(payment_address, 36):
    return "Unqualified payment address %s is not a 32 byte base58 encoded string." % payment_address

async def validateSourcePaymentAddress(pool_handle, wallet_handle, steward_did, source_payment_address,
                                       target_tokens_amount):
  logger.debug("Check for existence of token sources")
  token_sources = await getTokenSources(pool_handle, wallet_handle, steward_did, source_payment_address)

  if len(token_sources) == 0:
    err = Exception("No token sources found for source payment address %s" % source_payment_address)
    err.status_code = 400
    logging.error(err)
    raise err

  target_tokens_amount = target_tokens_amount or DEFAULT_TOKENS_AMOUNT
  logger.debug("Tokens amount to transfer >%s<", target_tokens_amount)

  if sum(source['amount'] for source in token_sources) < target_tokens_amount:
    err = Exception("No enough payment sources found to transfer %s tokens" % target_tokens_amount)
    err.status_code = 400
    logging.error(err)
    raise err

async def validateTargetPaymentAddress(pool_handle, wallet_handle, steward_did, target_payment_address):
  logger.debug("Check for not existence of token sources for target payment address")
  target_payment_sources = await getTokenSources(pool_handle, wallet_handle, steward_did, target_payment_address)

  if len(target_payment_sources) > 0:
    err = Exception(
      "Target payment address %s already contains payment sources %s. Payment address can't be used" % (
        target_payment_address, target_payment_sources))
    err.status_code = 409
    logging.error(err)
    raise err

def validateNym(nym):
  # Validate entry
  #
  # Must contain DID, verkey, sourceEmail, and targetPaymentAddress. All other fields are added by
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

  if 'targetPaymentAddress' in nym and nym.get('targetPaymentAddress') is not None:
    # Validate payment address
    error = isPaymentAddress(nym['targetPaymentAddress'])
    if error:
      errors.append(error)
  return errors

EXTENSION = {"darwin": ".dylib", "linux": ".so", "win32": ".dll", 'windows': '.dll'}

def file_ext():
  your_platform = platform.system().lower()
  return EXTENSION[your_platform] if (your_platform in EXTENSION) else '.so'

def loadPaymentLibrary():
  if not hasattr(loadPaymentLibrary, "loaded"):
    try:
      logger.debug("Before loading payment library")

      payment_plugin = cdll.LoadLibrary(PAYMENT_LIBRARY + file_ext())
      payment_plugin.sovtoken_init()
      loadPaymentLibrary.loaded = True

      logger.debug("After loading payment library")
    except Exception:
      err = Exception("Payment library %s could not found." % (PAYMENT_LIBRARY + file_ext()))
      err.status_code = 404
      logging.error(err)
      raise err

def trustAnchorNym(request, event):
  return {
    "DID": request['did'],
    "verkey": request['verkey'],
    "role": "TRUST_ANCHOR",
    "name": request['name'] if 'name' in request else " ",
    "sourceIP": event['requestContext']['identity']['sourceIp'],
    "sourceEmail": request['sourceEmail'],
    "targetPaymentAddress": request['targetPaymentAddress'],
    "tokensAmount": request['tokensAmount'],
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
  sourcePaymentAddressSeed = os.environ['SOURCE_PAYMENT_ADDRESS_SEED']

  ## TODO: Lock the handler down to just POST requests?
  # if event['httpMethod'] != 'POST':
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
      # stewardSeed = config['steward']['Seed']
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
    asyncio.ensure_future(addNYMs(future, poolName, genesisFile, stewardSeed, sourcePaymentAddressSeed, nyms))
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
      'Access-Control-Allow-Origin': '*'
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
  parser.add_argument('--source-payment-address-seed', action="store", dest="sourcePaymentAddressSeed",
                      default=None, help="A seed for source payment address containing tokens")
  parser.add_argument('--target-payment-address=', action="store", dest="targetPaymentAddress", default=None,
                      help="A target payment address related to DID to distribute tokens")
  parser.add_argument('--tokens-amount', action="store", dest="tokensAmount", default=DEFAULT_TOKENS_AMOUNT,
                      help="An amount of tokens to distribute to target payment address")
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
    "sourceEmail": args.sourceEmail,
    "targetPaymentAddress": args.targetPaymentAddress,
    "tokensAmount": args.tokensAmount,
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
                                  args.stewardSeed, args.sourcePaymentAddressSeed, nyms))
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
      'Access-Control-Allow-Origin': '*'
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
