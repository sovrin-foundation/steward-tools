# @author: Ryan West (ryan.west@sovrin.org)

# This script requires 4 parameters as follows:
#     pool_name   -  The name of the pool you created to attach to the
#       Sovrin Network (pool must already exist)
#     wallet_name -  The name of the wallet containing the DID used to
#       send ledger requests (wallet must already exist)
#     wallet_key  -  The secret key of <wallet_name>
#     signing_did -  The DID with sufficient rights to run
#       get-validator-info (must already be in the wallet <wallet_name>)

import asyncio
import argparse
from LocalLedger import LocalLedger
import LedgerQuery as lq


async def main():
    # check arguments
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument("pool_name", help="the pool you want to connect to.")
    parser.add_argument("wallet_name", help="wallet name to be used")
    parser.add_argument("wallet_key", help="wallet key for opening the wallet")
    parser.add_argument(
        "signing_did", help="did used to sign requests sent to the ledger")
    args = parser.parse_args()

    ll = LocalLedger("ledger_copy.db", args.pool_name, args.wallet_name,
                     args.wallet_key, args.signing_did)
    # establishes a connection with the pool object
    await ll.connect()
    # updates the pool till the most recent txn is reached (may take awhile)
    await ll.update()

    # test LedgerQuery functions using LocalLedger
    print('\nLedger count:', lq.getTxnCount(ll))

    lastTxn = lq.getTxn(ll, lq.getTxnCount(ll))
    print('Last sequence number:', lastTxn.getSeqNo())

    firstTxn = lq.getTxn(ll, 1)
    print('First txn seqNo:', firstTxn.getSeqNo())

    print('First txn as tuple:', firstTxn.asKeyValue())

    firstTxn2018 = lq.getTxn(ll, timestamp=1543647600)
    print('First txn in December 2018:', firstTxn2018.getSeqNo())

    janTxns = lq.getTxnRange(ll, startTime=1546326000, endTime=1549004400)
    print('Number of txns in January 2019:', len(janTxns))

    # test methods called on a dict of txns instead of a LocalLedger
    janFirstTxnSeqNo = lq.getTxn(janTxns, timestamp=546326000).getSeqNo()
    janLastTxnSeqNo = lq.getTxn(janTxns, timestamp=2649004400).getSeqNo()
    print('First/Last txn in Jan 2019:',
          janFirstTxnSeqNo, '/', janLastTxnSeqNo)

    failedFirsttxn = lq.getTxn(janTxns, seqNo=1)
    print('Txn seqno 1 from Jan2019 list (None since does not exist):',
          failedFirsttxn)

    # first timestamp purposely wrong but still returns correct value
    jan1Txns = lq.getTxnRange(janTxns, startTime=1000, endTime=1546412400)
    print('Number of txns in January 1st, 2019:', lq.getTxnCount(jan1Txns))

    # gets txn range from January txns by sequence numbers
    # janSeqRng = lq.getTxnRange(janTxns, startSeqNo=20200, endSeqNo=20201)

    # retrieves all txns by a certain did
    did = 'KvGE2tKSDuBXEkRc86dL4T'
    didTxns = lq.getDidTxns(ll, did)
    print('number of txns by did \'' + did + '\': ' + str(len(didTxns)))

    # retrieves all txns by a certain did from a dict of txns
    didTxns = lq.getDidTxns(janTxns, did)
    print('number of txns by did from january txns\'' +
          did + '\': ' + str(len(didTxns)))

    await ll.disconnect()

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
