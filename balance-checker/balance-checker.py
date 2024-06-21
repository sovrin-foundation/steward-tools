import argparse
import csv
import logging

from indy_helpers import *
from utils import *


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def read_input_data(data_file):
    expected_data = {}

    with open(data_file, 'r') as file:
        for row in csv.DictReader(file):
            expected_data[row["Payment Address"]] = int(row["Tokens Amount"])

    if len(expected_data) == 0:
        raise Exception('There is no a target payment address to check')

    return expected_data


def compare(expected_data, actual_data):
    failed = {}
    for payment_address, expected_amount in expected_data.items():
        actual_amount = actual_data[payment_address] if payment_address in actual_data else 0
        if expected_amount != actual_amount:
            failed[payment_address] = {'actual': actual_amount, 'expected': expected_amount}
    return failed


def run(args):
    # Input:
    # CSV File
    #       Payment Address, Tokens Amount
    #       address 1, 123
    #       address 2, 456
    #       address 3, 789
    #       .......
    #
    # Pool Genesis Transactions - interactive input
    #
    # Email Info File
    # {
    #   "host": "smtp.gmail.com",
    #   "port": 465,
    #   "from": "Sovrin@email.com",
    #   "subject": message subject,
    #   "body": message content
    # }
    print("Parsing expected data from CSV file: \"{}\" ...".format(args.dataFile))

    try:
        expected_data = read_input_data(args.dataFile)
    except Exception as err:
        raise Exception("Can not read input data file: {}".format(err))

    print("Connecting to Pool...")

    pool_handle = open_pool()

    logging.debug("Load Payment Library")

    load_payment_plugin()

    print("Getting payment sources from the ledger...")
    actual_data = get_payment_sources(pool_handle, expected_data.keys())

    print("Comparing values...")
    failed = compare(expected_data, actual_data)

    if len(failed) == 0:
        print('Token Balance checker work completed. No differences were found.')
    else:
        send_email(failed, args.emailInfoFile)

    logging.debug('Closing pool...')

    close_pool(pool_handle)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Script checks the ledger to ensure that the balance matches'
                                                 ' the expected values for each payment address listed in an input file')
    parser.add_argument('--dataFile',
                        help='[INPUT] .CSV file containing a list of payment addresses with an expected tokens amount'
                             '(columns: "Payment Address", "Tokens Amount")')
    parser.add_argument('--emailInfoFile', default=None,
                        help='[INPUT] .JSON file containing information required for email notifications')
    args = parser.parse_args()
    run(args)
