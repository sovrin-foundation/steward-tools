# @Author: Ryan West (ryan.west@sovrin.org)
import json
import logging
import json
import rocksdb
from indy import did, ledger, pool, wallet
from LocalLedger import LocalLedger
from Transaction import Transaction

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LedgerReader():
    '''
    Provides more advanced queries to downloaded ledger data, including by timestamp
    and by range in time or sequence number.
    Requires a LedgerDownloader object.
    '''

    def __init__(self, localLedger):
        self.l = localLedger
        if self.l == None:
            raise Exception('LocalLedger object must be provided') 

    def getTxn(self, seqNo=None, timestamp=None):
        '''Wrapper to get transaction by sequence number or timestamp''' 
        
        if seqNo == None and timestamp == None:
            raise Exception('Sequence number or timestamp required')
        if seqNo != None and timestamp != None:
            raise Exception('Cannot provide both sequence number and timestamp')

        if seqNo != None:
            return self.l.getTxn(seqNo)
        else:
            return self._getTxnByTimestamp(timestamp)

    def getTxnCount(self):
        '''Gets number of transactions stored in the database'''
        return self.l.getTxnCount()
        
    def _getTxnByTimestamp(self, timestamp):
        '''
        finds closest transaction that occurred after given POSIX timestamp
        returns (txn, seqNo)
        known bug: can't return txn seqNo <27 due to txn <17 with no timestamp
        '''
        txnCount = self.l.getTxnCount()

        if timestamp == None:
            return None

        def binarySearch(l, r, ts):
            # Check base case
            if r >= l:
                mid = l + (r - l) // 2
                curTxn = self.getTxn(mid)
                try:
                    txnTimestamp = curTxn['txnMetadata']['txnTime']
                except KeyError as e:
                    print('Txn' +  str(mid) + ': txnTime in txnMetadata not found, ', end='')
                    # bug: sometimes 'txnMetadata' cannot be found, but later it can be.
                    # first ~17 transactions have no timestamps because they are genesis
                    # txns. If the binary search encounters one of these first transactions,
                    # it will fail and return the first transaction.
                    if mid < 17:
                        print('Reason: This is a genesis transaction')
                        print('Returning first genesis transaction')
                        return self.getTxn(1)
                    else: 
                        print('Reason: Unknown')
                        print(json.dumps(curTxn, indent=4))
                        raise e

                #print('\n\n\nSearching TXN:', json.dumps(curTxn, indent=4))
                # If element is present at the middle itself
                if ts == txnTimestamp:
                    return curTxn
                # If element is smaller than mid, then it
                # can only be present in left subarray
                elif ts < txnTimestamp:
                    return binarySearch(l, mid - 1, ts)
                # Else the element can only be present
                # in right subarray
                else:
                    return binarySearch(mid + 1, r, ts)
            # if exact timestamp not found, return next in time
            else:
                return self.getTxn(l)
        
        txn = binarySearch(0, txnCount - 1, timestamp)
        seqNo = txn['txnMetadata']['seqNo']
        return seqNo, txn

    # get all transactions within a certain range
    def getTxnRange(self, startTime=None, endTime=None, startSeqNo=None, endSeqNo=None):
        '''
        Returns all transactions within a specified range of time. Can provide a 
        starting and ending timestamp or an exact start and end sequence number. Both
        start and end parameters are inclusive.
        '''
        if startSeqNo == None:
            startSeqNo, _ = self._getTxnByTimestamp(startTime) 
        if endSeqNo == None:
            endSeqNo, txn = self._getTxnByTimestamp(endTime) 
            # since getTxnByTimestamp returns the NEXT transaction at or after the given
            # timestamp, decrement ending sequence number if it is after the ending time
            if 'txnTime' in txn['txnMetadata'] and txn['txnMetadata']['txnTime'] > endTime:
                endSeqNo -= 1

        if startSeqNo < 1 or endSeqNo < startSeqNo or endSeqNo > self.getTxnCount():
            raise Exception("invalid start/end times")
        if startSeqNo == None or endSeqNo == None:
            raise Exception('Must specify a start and end') 

        txns = []

        curSeqNo = startSeqNo

        while curSeqNo <= endSeqNo:
            txns.append(self.getTxn(curSeqNo))
            curSeqNo += 1
        return txns


