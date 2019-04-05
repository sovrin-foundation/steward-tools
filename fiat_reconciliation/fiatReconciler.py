# @author: Ryan West (ryan.west@sovrin.org)

# This script requires 4 parameters as follows:
#     pool_name   -  The name of the pool you created to attach to the
#       Sovrin Network (pool must already exist)
#     wallet_name -  The name of the wallet containing the DID used to
#       send ledger requests (wallet must already exist)
#     wallet_key  -  The secret key of <wallet_name>
#     signing_did -  The DID with sufficient rights to run
#       get-validator-info (must already be in the wallet <wallet_name>)

import sys
sys.path.insert(0, '../local_ledger/')  # nopep8  # noqa
import ledger_query as lq
from local_ledger import LocalLedger
import asyncio
import argparse
import time
from datetime import datetime
import urllib.request

nymTxn = '1'
attribTxn = '100'
schemaTxn = '101'
credDefTxn = '102'


# Handles and parses all arguments, returning them
def parseArgs():
    helpTxt = 'You may optionally place each argument, line by line, in a\
        file, then read arguments from that file as so: \
        "python3 file.py @argumentFile.txt"'
    # ch.eck arguments
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@', epilog=helpTxt)
    parser.add_argument("pool_name", help="the pool you want to connect to.")
    parser.add_argument("wallet_name", help="wallet name to be used")
    parser.add_argument("wallet_key", help="wallet key for opening the wallet")
    parser.add_argument(
        "signing_did", help="did used to sign requests sent to the ledger")
    parser.add_argument(
        "start_date", help="mm-dd-yyyy time to start looking at txns")
    parser.add_argument(
        "end_date", help="mm-dd-yyyy time to stop looking at txns, inclusive")
    parser.add_argument(
        "database_dir", help="optional field to indicate which database dir",
        default="ledger_copy.db", nargs='?')
    return parser.parse_args()


# Converts a POSIX timestamp into a mm/dd/yyyy date
def getTimestampStr(date):
    return str(datetime.utcfromtimestamp(date).strftime('%m-%d-%Y'))


# Converts a mm/dd/yyyy string into a POSIX timestamp
def getTimestamp(dateStr):
    try:
        return time.mktime(datetime.strptime(dateStr, "%m-%d-%Y").timetuple())
    except ValueError:
        return time.mktime(datetime.strptime(dateStr, "%m/%d/%Y").timetuple())


# Connects to the specified ledger and updates it until the latest txn
# has been downloaded
async def loadTxnsLocally(args, startTimestamp, endTimestamp):
    print(args.database_dir)
    ll = LocalLedger(args.database_dir, args.pool_name, args.wallet_name,
                     args.wallet_key, args.signing_did)
    # first updates the local ledger database
    await ll.connect()
    await ll.update()
    await ll.disconnect()

    return lq.getTxnRange(ll, startTime=startTimestamp, endTime=endTimestamp)


# TODO: fix so this works when using fees that update over time
# Gets all txns within the specified period (using startTimeStamp and
# stopTimeStamp), then totals the fees for each txn type and prints them
def printFeesInPeriod(txns, txnsByType, fees, startTimestamp, endTimestamp):
    try:
        totalNymCost = fees['1'] * len(txnsByType[nymTxn])
    except Exception:
        totalNymCost = 0
    try:
        totalAttribCost = fees['100'] * len(txnsByType[attribTxn])
    except Exception:
        totalAttribCost = 0
    try:
        totalSchemaCost = fees['101'] * len(txnsByType[schemaTxn])
    except Exception:
        totalSchemaCost = 0
    try:
        totalCDCost = fees['102'] * len(txnsByType[credDefTxn])
    except Exception:
        totalCDCost = 0
    totalCost = totalNymCost + totalAttribCost + totalSchemaCost + totalCDCost

    startTimeStr = str(datetime.utcfromtimestamp(
        startTimestamp).strftime('%m-%d-%Y %H:%M:%S'))
    endTimeStr = str(datetime.utcfromtimestamp(
        endTimestamp).strftime('%m-%d-%Y %H:%M:%S'))

    # only list amounts if they are > 0
    print('Period: ' + startTimeStr + ' to ' + endTimeStr)
    print('Number of transactions in range:', len(txns),
          '\tTotal fees to be collected:', totalCost)
    if nymTxn in txnsByType:
        print('\tNym txns:', str(
            len(txnsByType[nymTxn])),
            '\t\t\tTotal fees to be collected:', str(totalNymCost))
    if attribTxn in txnsByType:
        print('\tAttribute txns:', str(len(
            txnsByType[attribTxn])),
            '\t\tTotal fees to be collected:', str(totalAttribCost))
    if schemaTxn in txnsByType:
        print('\tSchema txns:', str(len(
            txnsByType[schemaTxn])),
            '\t\tTotal fees to be collected:', str(totalSchemaCost))
    if credDefTxn in txnsByType:
        print('\tCredential def txns:', str(len(
            txnsByType[credDefTxn])),
            '\tTotal fees to be collected:', str(totalCDCost))


# Gets all the txns in the time period starting with startTimestamp and
# ending with endTimestamp, calculates how much every DID owner owes
# from that period (based on type and number of txns written), and prints this
# info to a csv file.
def outputBillsFile(startTimestamp, endTimestamp, bills):
    startTimeStr = getTimestampStr(startTimestamp)
    endTimeStr = getTimestampStr(endTimestamp)

    filename = 'billing ' + startTimeStr + ' to ' + endTimeStr + '.csv'
    with open(filename, 'w') as f:
        for key, value in sorted(bills.items()):
            f.write(str(key) + ',' + str(value) + '\n')

    print('Billing by did written to \'' + filename + '\'.')


# Looks at the Sovrin fiat fees spreadsheet (in csv format) and converts it
# into a dict to use when calculating fees over time (where the fees may have
# changed in the middle of a billing period)
def getFiatFees(csvFile='fiatFees.csv'):

    feesURL = 'https://docs.google.com/spreadsheets/d/1RFhQ4cOid7h_GoKZKNXudDSlFoyhbyq5U4gsqW4gthE/export?format=csv'  # noqa

    # downloads the fees.csv file from Google Sheets
    urllib.request.urlretrieve(feesURL, 'fiatFees.csv')
    # opens the file just downloaded (unless another is chosen) to read from
    with open(csvFile, 'r') as file:
        lines = file.readlines()

    if len(lines) == 0:
        raise Exception('No fee information found')

    # remove header column, if it exists
    if lines[0].startswith('Date'):
        lines.pop(0)

    feesByTimePeriod = {}

    for line in lines:
        data = line.split(',')
        if len(data) != 8:
            raise Exception('Wrong format for fees csv file')

        timestamp = getTimestamp(data[0])
        nymFee = float(data[2])
        attribFee = float(data[3])
        schemaFee = float(data[4])
        credDefFee = float(data[5])
        # Revocation registry is disabled on mainnet for now; ignore these
        # revocRegFee = float(data[6])
        # revogRegUpdateFee = float(data[7])

        feesByTimePeriod[timestamp] = {
            nymTxn: nymFee,
            attribTxn: attribFee,
            schemaTxn: schemaFee,
            credDefTxn: credDefFee
            # more will be added when revocation is supported
        }

    return feesByTimePeriod


# Calculates the bill amount for each did in the time period, checking for
# fee updates based on the Sovrin fees spreadsheet on Google Sheets
# TODO: add way to check if txn was token-based or fiat-based
def calculateBills(feesByTimePeriod, txns):
    # dict of all DIDs who owe money for the current period
    # in the form key: did, val: amount
    bills = {}

    def _getFeeForTxn(txn, feesByTimePeriod):
        lastTimestamp = 0
        txnTimestamp = txn.getTime()
        # if there is no timestamp, then it is most likely a genesis txn so
        # do not charge anything
        if txnTimestamp is None:
            return 0
        for timestamp, fees in sorted(feesByTimePeriod.items()):
            if txnTimestamp < timestamp:
                break
            lastTimestamp = timestamp

        if lastTimestamp == 0:
            raise Exception('No fees found for transaction timestamp')

        return feesByTimePeriod[lastTimestamp][txn.getType()]

    for t in txns.values():
        # populate bills dict
        if t.getSenderDid() not in bills:
            bills[t.getSenderDid()] = _getFeeForTxn(t, feesByTimePeriod)
        else:
            bills[t.getSenderDid()] += _getFeeForTxn(t, feesByTimePeriod)

    # If authorless genesis txns are in the range, we don't include these
    bills.pop(None, None)

    for b in bills:
        if b == 0:
            print(b)
    return bills


async def main():

    args = parseArgs()

    # convert input args to timestamps
    startTimestamp = getTimestamp(args.start_date)
    endTimestamp = getTimestamp(args.end_date)

    # all transactions in the specified range
    txns = await loadTxnsLocally(args, startTimestamp, endTimestamp)

    # transactions separated by type in the format key: type, val: list(txns)
    txnsByType = {}

    for t in txns.values():
        # populate txnsByType dict
        if t.getType() not in txnsByType:
            txnsByType[t.getType()] = [t]
        else:
            txnsByType[t.getType()].append(t)

    # retrive fiat fees
    feesByTimePeriod = getFiatFees()
    # printFeesInPeriod(txns, txnsByType, feesByTimePeriod,
    #                  startTimestamp, endTimestamp)
    bills = calculateBills(feesByTimePeriod, txns)
    outputBillsFile(startTimestamp, endTimestamp, bills)

    return sorted(bills.items())
    # Prints all schema keys
    # for t in txnsByType['102']:
    #    print('\n\n')
    #    t.printKeys()


if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
