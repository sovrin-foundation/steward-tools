# @author: Ryan West (ryan.west@sovrin.org)

# This script requires 4 parameters as follows:
#     pool_name   -  The name of the pool you created to attach to the Sovrin Network (pool must already exist)
#     wallet_name -  The name of the wallet containing the DID used to send ledger requests (wallet must already exist)
#     wallet_key  -  The secret key of <wallet_name>
#     signing_did -  The DID with sufficient rights to run get-validator-info (must already be in the wallet <wallet_name>)

import asyncio
import logging
import argparse
import rocksdb
import time
import datetime

import sys
sys.path.insert(0, '../local_ledger/')

from LedgerDownloader import LedgerDownloader
from LedgerReader import LedgerReader

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def main():

    # check arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("pool_name", help="the pool you want to connect to.")
    parser.add_argument("wallet_name", help="wallet name to be used")
    parser.add_argument("wallet_key", help="wallet key for opening the wallet")
    parser.add_argument("signing_did", help="did used to sign requests sent to the ledger")
    parser.add_argument("start_date", help="dd/mm/yyyy time to start looking at txns")
    parser.add_argument("end_date", help="dd/mm/yyyy time to stop looking at txns, inclusive")
    args = parser.parse_args()

    ld = LedgerDownloader("ledger_copy.db", args.pool_name, args.wallet_name, args.wallet_key, 
                          args.signing_did)
    await ld.connect()
    await ld.update()
    
    lr = LedgerReader(ld)

    # TODO: verify timezone correctness
    startTimestamp = time.mktime(datetime.datetime.strptime(args.start_date, "%d/%m/%Y").timetuple())
    endTimestamp = time.mktime(datetime.datetime.strptime(args.end_date, "%d/%m/%Y").timetuple())

    txns = lr.getTxnRange(startTime=startTimestamp, endTime=endTimestamp)
    

    txnTypes = {}

    for t in txns:
        txnType = t['txn']['type'] 
        if txnType not in txnTypes:
            txnTypes[txnType] = 1
        else:
            txnTypes[txnType] += 1

    nymTxn = '1'
    attribTxn = '100'
    schemaTxn = '101'
    credDefTxn = '102'

    nymCost = 10
    attribCost = 10
    schemaCost= 50
    credDefCost = 25

    totalNymCost = nymCost * txnTypes[nymTxn]
    totalAttribCost = attribCost * txnTypes[attribTxn]
    totalSchemaCost = schemaCost * txnTypes[schemaTxn]
    totalCredDefCost = credDefCost * txnTypes[credDefTxn] 
    totalCost = totalNymCost + totalAttribCost + totalSchemaCost + totalCredDefCost

    print('\nNumber of transactions in range:', len(txns), '\tTotal fees to be collected:', totalCost)
    print('\tNym txns:', str(txnTypes[nymTxn]), '\t\t\tTotal fees to be collected:', str(totalNymCost))
    print('\tAttribute txns:', str(txnTypes[attribTxn]), '\t\tTotal fees to be collected:', str(totalAttribCost))
    print('\tSchema txns:', str(txnTypes[schemaTxn]), '\t\tTotal fees to be collected:', str(totalSchemaCost))
    print('\tCredential definition txns:', str(txnTypes[credDefTxn]), '\tTotal fees to be collected:', str(totalCredDefCost))
    

    await ld.disconnect()

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
