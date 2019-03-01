# Author: Ryan West (ryan.west@sovrin.org)
import asyncio
import json
import logging
import json
import rocksdb
import os
from indy import did, ledger, pool, wallet
from pprint import pprint

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TxnDoesNotExistException(Exception):
    pass

class InvalidLedgerResponseException(Exception):
    pass

class Transaction():

    def __init__(self, data):
        self.data = data

        if 'data' in self.data:
            print('Wrong format: ') #str(self.getSeqNo()))
            self.print()

    def getType(self):
        try:
            return self.data['txn']['type']
        except KeyError:
            return None
            
    def getTime(self):
        try:
            return self.data['txnMetadata']['txnTime']
        except KeyError:
            return None

    def getSeqNo(self):
            try:
                return self.data['txnMetadata']['seqNo']
        except KeyError:
            return None

    def getSenderDid(self):
        try:
            return self.data['txn']['metadata']['from']
        except KeyError:
            return None

    def print(self):
        print(json.dumps(self.data, indent=4))

    def printKeys(self):
        self._printInnerKeys(self.data, 0) 

    def _printInnerKeys(self, d, indentLevel):
        for key, value in d.items():
                print(('  ' * indentLevel) + '\'' + str(key) + '\'')
                if isinstance(value, dict):
                    self._printInnerKeys(value, indentLevel + 1)
 

    def __setitem__(self, key, item):
        self.data[key] = item

    def __getitem__(self, key):
        return self.data[key]

    def __repr__(self):
        return repr(self.data)

    def __str__(self):
        return str(self.data)

    def __len__(self):
        return len(self.data)

    def __delitem__(self, key):
        del self.data[key]



# TODO: add option to download specific set of transactions instead of all at once
# TODO: download faster (why is there a delay after every 5 requests?)
class LedgerDownloader():
    ''' 
    Uses a rocksdb key-value database to download and store an indy network ledger
    Automatically downloads all transactions as they are added on the net
    Allows for simple transaction reading by sequence number
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
        # _db should not be modified directly, as len(_db) may no longer be accurate
        self._db = rocksdb.DB(databaseDir, rocksdb.Options(create_if_missing=True))
        self.pool_handle = None
        self.wallet_handle = None

        
    async def connect(self):
        '''Connects to the pool specified in the constructor, using given wallet and did'''
        #logger.info("==============================")
        #logger.info("=== Connecting to pool ===")
        #logger.info("------------------------------")
        # Set protocol version 2 to work with Indy Node 1.4
        await pool.set_protocol_version(2)

        config = {} 
        creds = {}
        config["id"] = self.walletname
        creds ["key"]= self.key

        self.pool_handle   = await pool.open_pool_ledger(self.poolname, None)
        self.wallet_handle = await wallet.open_wallet(json.dumps(config),json.dumps(creds))

    async def disconnect(self):
        '''Closes indy wallet and pool connections'''
        #logger.info("Close pool and wallet")
        await wallet.close_wallet(self.wallet_handle)
        await pool.close_pool_ledger(self.pool_handle)


    
    async def downloadTxn(self, pool_handle, submitter_did, which_ledger, seq_no):
        '''Attempts to download the transaction with given sequence number'''
        # build get_txn request
        getTxnJson = await ledger.build_get_txn_request(submitter_did, which_ledger, seq_no)
        # get response from ledger
        response = await ledger.submit_request(pool_handle, getTxnJson)
        # serialize json into object
        responseJson = json.loads(response)['result']

        # if we're at the last txn on the ledger, stop trying to download more
        if responseJson['data'] == None:
            raise TxnDoesNotExistException()

        try:
            key = responseJson['seqNo']
            value = responseJson['data']
        except:
            print('\nError in response message:')
            print('\n', json.dumps(json.loads(response), indent=4))
            raise InvalidLedgerResponseException() 
         
        self._db.put(self.intToBytes(key), json.dumps(value).encode())


    async def update(self):
        ''' Downlads new transactions to update local db with remote'''
            
        # gets the last sequence number stored locally and updates from there
        curTxn = self.getTxnCount() + 1
        if curTxn == None:
            curTxn = 1
        print('Last transaction sequence number:', str(curTxn - 1))
        printedDownload = False
        while True:
            try:
                await self.downloadTxn(self.pool_handle, self.did, 'DOMAIN', curTxn)
            except TxnDoesNotExistException:
                #print('\n')
                break

            if not printedDownload:
                print('Downloading new transactions', end='')
                printedDownload = True
            print('.', end='', flush=True)
            self.updateTxnCount(curTxn)
            # Keep track of the most recent transaction sequence number
            curTxn += 1

        print('Local ledger copy is up to date.')
 
    def intToBytes(self, x):
        return x.to_bytes((x.bit_length() + 7) // 8, 'big')

    def updateTxnCount(self, count):
        '''Updates the transaction count (stored as a key-value pair in db)'''
        self._db.put(b'lastTxnDownloaded', int.to_bytes(count, 10, byteorder='big'))

    def getTxnCount(self):
        '''Gets the number of transactions'''
        try:
            return int.from_bytes(self._db.get(b'lastTxnDownloaded'), byteorder='big')
        except Exception:
            return 0

    def getTxn(self, seqNo):
        '''Retrieves a transaction with its sequence number in a tuple'''
        try:
            return json.loads(self._db.get(self.intToBytes(seqNo)).decode('ascii')) 
        except AttributeError:
            return None


