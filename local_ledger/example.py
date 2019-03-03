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
from LedgerDownloader import LedgerDownloader
from LedgerReader import LedgerReader

async def main():

    # check arguments
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument("pool_name", help="the pool you want to connect to.")
    parser.add_argument("wallet_name", help="wallet name to be used")
    parser.add_argument("wallet_key", help="wallet key for opening the wallet")
    parser.add_argument("signing_did", help="did used to sign requests sent to the ledger")
    args = parser.parse_args()

    ld = LedgerDownloader("ledger_copy.db", args.pool_name, args.wallet_name, args.wallet_key, 
                          args.signing_did)
    await ld.connect()
    await ld.update()
    
    lr = LedgerReader(ld)

    print('Last Transaction Received:')
    print(lr.getTxn(lr.getTxnCount()))

    await ld.disconnect()

if __name__ == '__main__':
    try:
        # TODO: move this into LedgerDownloader (with option to have external loop instead)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
