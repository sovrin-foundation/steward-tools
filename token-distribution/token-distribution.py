import argparse
import logging

from indy_helpers import *
from utils import *


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def parse_input_data(file) -> (dict, list):
    logging.debug("Parse input CSV file: {}".format(args.dataFile))

    data = read_csv_file(file)

    if len(data) == 0:
        raise Exception('File is empty')

    owner_info = data.pop(0)

    source = {
        'paymentAddress': owner_info[0],
        'walletId': owner_info[1],
        'walletPath': owner_info[2]
    }

    if len(data) == 0:
        raise Exception('There is no any target payment in the document')

    targets = [
        {
            'legalName': row[0],
            'tokensAmount': row[1],
            'paymentAddress': row[2],
            'email': row[3]
        }
        for row in data]
    return source, targets


def prepare_payment_data(source_payment_address, sources, targets):
    outputs = []
    required_tokens = 0

    for target in targets:
        target_amount = int(target['tokensAmount'])
        outputs.append({
            'recipient': target['paymentAddress'],
            'amount': target_amount
        })
        required_tokens += target_amount

    inputs = []
    source_amount = 0

    for source in sources:
        if source_amount < required_tokens:
            inputs.append(source['source'])
            source_amount += source['amount']
        else:
            break

    if source_amount < required_tokens:
        raise Exception('Insufficient funds on inputs: required: {}, source: {}'.format(required_tokens, source_amount))

    if source_amount > required_tokens:
        outputs.append({
            'recipient': source_payment_address,
            'amount': source_amount - required_tokens
        })

    return inputs, outputs


def ask_user_confirmation():
    answer = input("Would you like to continue? y/n     ")
    if answer == 'y' or answer == 'yes':
        pass
    else:
        raise Exception('Action has been interrupted')


def print_targets(items):
    delimiter = "-" * 150

    total_tokens = 0
    total_targets = 0

    print(delimiter)
    print("{:<30} {:<15} {:<60}".format('Target Name', 'Tokens Amount', 'Payment Address'))
    print(delimiter)
    for item in items:
        print("{:<30} {:<15} {:<60}".format(item['legalName'], item['tokensAmount'], item['paymentAddress']))
        print(delimiter)

        total_tokens += int(item['tokensAmount'])
        total_targets += 1

    print("Total number of addresses: " + str(total_targets))
    print("Total number of tokens: " + str(total_tokens))
    print()


def ensure_payment_transaction_result(pool_handle, response, targets):
    logging.debug("Load Payment Library")

    load_payment_plugin()

    receipts = parse_payment_response(response)
    to_verifies = []

    for target in targets:
        matches = [receipt for receipt in receipts if target["paymentAddress"] == receipt['recipient']]
        if len(matches) != 1:
            raise Exception('Payment failed for {}'.format(target["paymentAddress"]))
        to_verifies.append(matches[0]['receipt'])

    verify_payment_on_ledger(pool_handle, to_verifies)


def prepare(args):
    # Input:
    # CSV File
    #       Payment Address, Wallet Id, Wallet Path   -  Actually ONLY Payment Address is needed on this step.
    #                                                    Wallet info is needed only on the next step
    #       Legal Name, Tokens Amount, Email, Payment Address
    #       Legal Name, Tokens Amount, Email, Payment Address
    #       Legal Name, Tokens Amount, Email, Payment Address
    #       .......
    #
    # Pool Genesis Transactions - interactive input
    #
    # Output - JSON file as ZIP archive
    # {
    #   walletInfo: {
    #       walletId
    #       walletPath
    #   }
    #   inputs
    #   outputs
    #   targets
    # }
    print("Parsing input data from CSV file: \"{}\" ...".format(args.dataFile))

    sender_info, targets = parse_input_data(args.dataFile)

    print("The following list of target payments has been parsed")

    print_targets(targets)

    ask_user_confirmation()

    print("Connecting to Pool...")

    pool_handle = open_pool()

    logging.debug("Load Payment Library")

    load_payment_plugin()

    print("Preparing data for payment transaction...")

    logging.debug("Get payment sources for payment address \"{}\"".format(sender_info['paymentAddress']))

    sources = get_payment_sources(pool_handle, sender_info['paymentAddress'])

    inputs, outputs = prepare_payment_data(sender_info['paymentAddress'], sources, targets)

    next_step_data = {
        'walletInfo': {
            'walletPath': sender_info['walletPath'],
            'walletId': sender_info['walletId']
        },
        'inputs': inputs,
        'outputs': outputs,
        'targets': targets,
    }

    print("Saving results into a file...")

    store_zip_file(json.dumps(next_step_data))

    logging.debug("Closing pool...")

    close_pool(pool_handle)


def build(args):
    # Input:
    # ZIP archive containing JSON File
    # {
    #   walletInfo: {
    #       walletId
    #       walletPath
    #   }
    #   inputs
    #   outputs
    #   targets
    # }
    #
    # Wallet Key - interactive input
    #
    # Output - JSON file as ZIP archive
    # {
    #   transaction
    #   targets
    # }

    print("Parsing input data from ZIP archive: \"{}\" ...".format(args.dataFile))

    data = json.loads(read_zip_file(args.dataFile))

    print("The following list of target payments has been parsed")

    print_targets(data['targets'])

    ask_user_confirmation()

    print("Opening wallet...")

    wallet_handle = open_wallet(data['walletInfo'])

    logging.debug("Load Payment Library")

    load_payment_plugin()

    print("Building and Signing Payment Transaction...")

    transaction = build_payment_request(wallet_handle, data['inputs'], data['outputs'])

    logging.debug("Closing wallet")

    close_wallet(wallet_handle)

    next_step_data = {
        'transaction': transaction,
        'targets': data['targets']
    }

    print("Saving results into a file...")

    store_zip_file(json.dumps(next_step_data))


def publish(args):
    # Input:
    # ZIP archive containing JSON File
    # {
    #   transaction
    #   targets
    # }
    # Email Info File
    #
    # Pool Genesis Transactions - interactive input

    print("Parsing input data from ZIP archive: \"{}\" ...".format(args.dataFile))

    data = json.loads(read_zip_file(args.dataFile))

    print("The following list of target payments has been parsed")

    print_targets(data['targets'])

    ask_user_confirmation()

    print("Connecting to Pool...")

    pool_handle = open_pool()

    print("Sending Payment Transaction...")

    response = send_transaction(pool_handle, data['transaction'])

    print("Checking result of transaction...")

    ensure_payment_transaction_result(pool_handle, response, data['targets'])

    print("Sending emails to recipients...")

    send_emails(data['targets'], args.emailInfoFile)

    logging.debug("Closing pool")

    close_pool(pool_handle)


def send_emails(targets, email_info_file):
    try:
        email_info = json.loads(read_file(email_info_file))
    except Exception as err:
        print("No information for email sending found: {}".format(err))
        return

    password = getpass("Enter Password for Email Account \"{}\":   ".format(email_info['from']))

    print("-" * 50)

    targets = [{
                   'to': target['email'],
                   'body': "{} {} {}".format(target['tokensAmount'], email_info['body'], target['paymentAddress'])
               }
               for target in targets if target['email']]

    send_email(email_info['from'], targets, email_info['subject'], password)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', default=None,
                        choices=["prepare", "build", "publish"],
                        help="Type of action to perform")
    parser.add_argument('--dataFile',
                        help='[INPUT] file containing information required for action performing')
    parser.add_argument('--emailInfoFile', default=None,
                        help='[INPUT] file containing information required for email sending')
    args = parser.parse_args()

    if args.action == 'prepare':
        prepare(args)
    elif args.action == 'build':
        build(args)
    elif args.action == 'publish':
        publish(args)
    else:
        pass
