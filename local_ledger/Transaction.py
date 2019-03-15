import json


# Helper class which stores transaction json and allows easy interaction
class Transaction():

    def __init__(self, data):
        self.data = data

        if 'data' in self.data:
            raise Exception('Wrong Transaction format')

    def getType(self):
        '''Returns the transaction type (NYM, CRED_DEF, etc)'''
        try:
            return self.data['txn']['type']
        except KeyError:
            return None

    def getTime(self):
        '''Returns the timestamp for which the transaction was created'''
        try:
            return self.data['txnMetadata']['txnTime']
        except KeyError:
            return None

    def getSeqNo(self):
        '''Gets the sequence number of the txn, which is also its key'''
        try:
            return self.data['txnMetadata']['seqNo']
        except KeyError:
            return None

    def getSenderDid(self):
        '''Gets the did of the transaction author'''
        try:
            return self.data['txn']['metadata']['from']
        except KeyError:
            return None

    def asKeyValue(self):
        '''Returns the transaction in a tuple as (seqNo, txn), as it is stored
           in a rocksdb database'''
        key = self.getSeqNo()
        value = self
        return key, value

    def print(self):
        '''Pretty prints the full json of the transaction'''
        print(json.dumps(self.data, indent=4))

    def printKeys(self):
        '''Prints all keys in all dicts, indenting to indicate inner dicts'''
        self._printInnerKeys(self.data, 0)

    def _printInnerKeys(self, d, indentLevel):
        for key, value in d.items():
            print(('  ' * indentLevel) + '\'' + str(key) + '\'')
            if isinstance(value, dict):
                self._printInnerKeys(value, indentLevel + 1)

    '''
    The methods  below allow a transaction to be treated like a dict
    directly. For example: Get transaction t's seqNo like this:
        t['txnMetadata']['seqNo']
    '''

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
