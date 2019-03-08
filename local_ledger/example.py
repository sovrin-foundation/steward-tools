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
from LocalLedger import LocalLedger
import LedgerQuery as lq

async def main():

    # check arguments
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument("pool_name", help="the pool you want to connect to.")
    parser.add_argument("wallet_name", help="wallet name to be used")
    parser.add_argument("wallet_key", help="wallet key for opening the wallet")
    parser.add_argument("signing_did", help="did used to sign requests sent to the ledger")
    args = parser.parse_args()

    l = LocalLedger("ledger_copy.db", args.pool_name, args.wallet_name, args.wallet_key, 
                          args.signing_did)
    await l.connect()
    await l.update()
    
    # test LedgerQuery functions using LocalLedger
    print('Ledger count:', lq.getTxnCount(l))

    lastTxn = lq.getTxn(l, lq.getTxnCount(l))
    print('Last sequence number:', lastTxn.getSeqNo())

    firstTxn = lq.getTxn(l, 1)
    print('First txn seqNo:', firstTxn.getSeqNo())

    print('First txn as tuple:', firstTxn.asKeyValue())

    firstTxn2018 = lq.getTxn(l, timestamp=1543647600)
    print('First txn in December 2018:', firstTxn2018.getSeqNo())


    janTxns = lq.getTxnRange(l, startTime=1546326000, endTime=1549004400)
    print('Number of txns in January 2019:', len(janTxns))
    #print(janTxns.keys())
    # test methods called on a dict of txns instead of a LocalLedger
    janFirstTxnSeqNo = lq.getTxn(janTxns, timestamp=546326000).getSeqNo()
    janLastTxnSeqNo = lq.getTxn(janTxns, timestamp=2649004400).getSeqNo()
    print('First/Last txn in Jan 2019:', janFirstTxnSeqNo, '/', janLastTxnSeqNo)

    # first timestamp purposely wrong but still returns correct value 
    jan1Txns = lq.getTxnRange(janTxns, startTime=1000, endTime=1546412400)
    print('Number of transactions in January 1st, 2019:', lq.getTxnCount(jan1Txns)) 

    janSeqRng = lq.getTxnRange(janTxns, startSeqNo=20200, endSeqNo=20201)
    #print(janSeqRng)

    didTxns = lq.getDidTxns(l, 'QAxGCiizb9VZNiwZEBJzon')
    print(didTxns)

    await l.disconnect()

if __name__ == '__main__':
    try:
        # TODO: move this into LedgerDownloader (with option to have external loop instead)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
