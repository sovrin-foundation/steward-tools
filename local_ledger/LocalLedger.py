# Author: Ryan West (ryan.west@sovrin.org)
import json
import rocksdb
import os
from indy import ledger, pool, wallet
from Transaction import Transaction


class TxnDoesNotExistException(Exception):
    pass


class InvalidLedgerResponseException(Exception):
    pass


# TODO: add option to download specific set of txns instead of all
class LocalLedger():
    '''
    Uses a rocksdb key-value db to download and store an indy network ledger
    Automatically downloads all transactions as they are added on the net
    Allows for simple transaction reading by sequence number

    NOTE: Currently this uses an indy GET_TXN request for every txn on ledger.
    This is slow and extremely chatty, and should eventually be replaced with
    a batch message request or catchup solutions; however, these options still
    need to be implemented in indy-sdk.
    '''

    def __init__(self, filename, poolname, walletname, key, did):
        '''Setup for inital use'''
        self.filename = filename
        self.poolname = poolname
        self.walletname = walletname
        self.key = key
        self.did = did
        databaseDir = 'ledger_copy.db'
        if not os.path.isdir(databaseDir):
            print('Local ledger database not found; creating a new one')
        # _db should not be modified directly, as len(_db) may no longer
        # be accurate
        self._db = rocksdb.DB(
            databaseDir, rocksdb.Options(create_if_missing=True))
        self.pool_handle = None
        self.wallet_handle = None

    async def connect(self):
        '''Connects to the pool specified in the constructor, using given
        wallet and did'''

        await pool.set_protocol_version(2)

        config = {}
        creds = {}
        config["id"] = self.walletname
        creds["key"] = self.key

        self.pool_handle = await pool.open_pool_ledger(self.poolname, None)
        self.wallet_handle = await wallet.open_wallet(json.dumps(config),
                                                      json.dumps(creds))

    async def disconnect(self):
        '''Closes indy wallet and pool connections'''

        await wallet.close_wallet(self.wallet_handle)
        await pool.close_pool_ledger(self.pool_handle)

    async def downloadTxn(self, pool_handle, submitter_did, which_ledger,
                          seq_no):
        '''Attempts to download the transaction with given sequence number'''

        # build get_txn request
        getTxnJson = await ledger.build_get_txn_request(submitter_did,
                                                        which_ledger, seq_no)
        # get response from ledger
        response = await ledger.submit_request(pool_handle, getTxnJson)
        # serialize json into object
        responseJson = json.loads(response)['result']

        # if we're at the last txn on the ledger, stop trying to download more
        if responseJson['data'] is None:
            raise TxnDoesNotExistException()

        try:
            key = responseJson['seqNo']
            value = responseJson['data']
        except Exception:
            print('\nError in response message:')
            print('\n', json.dumps(json.loads(response), indent=4))
            raise InvalidLedgerResponseException()

        self._db.put(self._intToBytes(key), json.dumps(value).encode())

    async def update(self):
        ''' Downlads new transactions to update local db with remote'''

        # gets the last sequence number stored locally and updates from there
        curTxn = self.getTxnCount() + 1
        if curTxn is None:
            curTxn = 1
        print('Last transaction sequence number:', str(curTxn - 1))
        printedDownload = False
        while True:
            try:
                await self.downloadTxn(self.pool_handle, self.did,
                                       'DOMAIN', curTxn)
            # if there is no txn, we've reached the most recent one so break
            except TxnDoesNotExistException:
                break

            if not printedDownload:
                print('Downloading new transactions', end='')
                printedDownload = True
            print('.', end='', flush=True)
            self.updateTxnCount(curTxn)
            # Keep track of the most recent transaction sequence number
            curTxn += 1

        print('Local ledger copy is up to date.')

    def _intToBytes(self, x):
        return x.to_bytes((x.bit_length() + 7) // 8, 'big')

    def updateTxnCount(self, count):
        '''Updates the transaction count (stored as a key-value pair in db)'''

        self._db.put(b'lastTxnDownloaded', int.to_bytes(
            count, 10, byteorder='big'))

    def getTxnCount(self):
        '''Gets the number of transactions'''

        try:
            return int.from_bytes(self._db.get(b'lastTxnDownloaded'),
                                  byteorder='big')
        except Exception:
            return 0

    def getTxn(self, seqNo):
        '''Retrieves a transaction with its sequence number in a tuple'''

        try:
            return Transaction(json.loads(self._db.get(self._intToBytes(seqNo))
                               .decode('ascii')))
        # if the sequence number isn't a key in the database, return nothing
        except AttributeError:
            return None
