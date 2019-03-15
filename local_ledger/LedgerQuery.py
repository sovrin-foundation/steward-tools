# @Author: Ryan West (ryan.west@sovrin.org)
import json
from LocalLedger import LocalLedger


'''
Provides more advanced queries to downloaded ledger data, including by time
and by range in time or sequence number.
Requires a LedgerDownloader object.
'''


def getTxn(ledger, seqNo=None, timestamp=None):
    '''Wrapper to get transaction by sequence number or timestamp'''

    if ledger is None:
        raise Exception('LocalLedger object must be provided')

    if seqNo is None and timestamp is None:
        raise Exception('Sequence number or timestamp required')
    if seqNo is not None and timestamp is not None:
        raise Exception('Cannot provide both sequence number and timestamp')

    if isinstance(ledger, dict):
        if seqNo is not None:
            if seqNo in ledger:
                return ledger[seqNo]
        else:
            _, txn = _getTxnByTimestamp(ledger, timestamp)
            return txn
    elif isinstance(ledger, LocalLedger):
        if seqNo is not None:
            return ledger.getTxn(seqNo)
        else:
            _, txn = _getTxnByTimestamp(ledger, timestamp)
            return txn
    else:
        raise Exception('ledger parameter must be of type dict or LocalLedger')


def getTxnCount(ledger):
    '''Gets number of transactions stored in the database'''

    if 'getTxnCount' in dir(ledger):
        return ledger.getTxnCount()
    else:
        return len(ledger)


def _getTxnByTimestamp(ledger, timestamp, contiguous=True):
    '''
    finds closest transaction that occurred after given POSIX timestamp
    returns (txn, seqNo)
    contiguous: if using a dict as input instead of LocalLedger and the dict
        does not contain all transactions from one point in time to another,
        this must be set to false or the method may fail. This slows down
        search time.
    known bug: can't return txn seqNo <27 due to txn <17 with no timestamp
    '''

    if timestamp is None:
        return None

    def binarySearch(l, r, ts):
        # Check base case
        if r >= l:
            mid = l + (r - l) // 2
            curTxn = getTxn(ledger, mid)
            try:
                txnTimestamp = curTxn.getTime()
                if txnTimestamp is None:
                    raise Exception('txntimestamp returned None')
            except (KeyError, Exception) as e:
                print('Txn ' + str(mid) +
                      ': txnTime in txnMetadata not found, ', end='')
                # first ~17 txns have no timestamps because they are genesis
                # txns. If the binary search encounters one of these txns,
                # it will fail and return the first transaction.
                if mid < 17:
                    print('Reason: This is a genesis transaction')
                    print('Returning first genesis transaction')
                    return getTxn(ledger, 1)
                else:
                    print('Reason: Unknown (Transaction JSON below)')
                    print(json.dumps(curTxn, indent=4))
                    raise e

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
            return getTxn(ledger, l)

    # if using LocalLedger, then all txns from the first are stored
    # contiguously
    if isinstance(ledger, LocalLedger):
        highest = getTxnCount(ledger) - 1
        lowest = 0
    elif isinstance(ledger, dict):
        if contiguous:
            lowest = min(ledger.keys())
            highest = max(ledger.keys()) - 1
        else:
            raise Exception('noncontiguous not yet implemented')
    txn = binarySearch(lowest, highest, timestamp)
    seqNo = txn.getSeqNo()
    return seqNo, txn


def getTxnRange(ledger, startTime=None, endTime=None,
                startSeqNo=None, endSeqNo=None):
    '''
    Returns all transactions within a specified range of time. Can provide a
    starting and ending timestamp or an exact start and end sequence number.
    Both start and end parameters are inclusive.
    '''
    if startSeqNo is None:
        startSeqNo, _ = _getTxnByTimestamp(ledger, startTime)
    if endSeqNo is None:
        endSeqNo, txn = _getTxnByTimestamp(ledger, endTime)
        # since getTxnByTimestamp returns the NEXT transaction at or after the
        # given timestamp, decrement ending sequence number if it is after the
        # ending time
        if 'txnTime' in txn['txnMetadata'] and \
                txn['txnMetadata']['txnTime'] > endTime:
            endSeqNo -= 1
    if startSeqNo < 1 or endSeqNo < startSeqNo:
        if ((isinstance(ledger, LocalLedger) and
                endSeqNo > getTxnCount(ledger)) or isinstance(ledger, dict and
                endSeqNo > max(ledger.keys()))):  # nopep8
            raise Exception("invalid start/end times")
    if startSeqNo is None or endSeqNo is None:
        raise Exception('Must specify a start and end')

    txns = {}

    curSeqNo = startSeqNo

    while curSeqNo <= endSeqNo:
        txns[curSeqNo] = getTxn(ledger, curSeqNo)
        curSeqNo += 1
    return txns


def getDidTxns(ledger, did):
    '''
    Returns all transactions from the ledger object that are owned by the
    specified did. The ledger can be a LocalLedger or a dict of transactions.
    '''
    if isinstance(ledger, LocalLedger):
        txns = getTxnRange(ledger, startSeqNo=1, endSeqNo=ledger.getTxnCount())
        txns = txns.values()
    elif isinstance(ledger, dict):
        txns = ledger.values()

    didTxns = {}
    for t in txns:
        if t.getSenderDid() == did:
            didTxns[t.getSeqNo()] = t

    return didTxns
