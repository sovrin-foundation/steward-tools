class Transaction():

    def __init__(self, data):
        self.data = data

        if 'data' in self.data:
            self.print()
            raise Exception('Wrong Transaction format')

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


