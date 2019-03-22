# Local Ledger Tool

This tool allows you to download a copy of a specified ledger to your local machine. It also provides methods for different types of queries on the local copy.

This tool is still being developed and should not be used in production for the time being. Downloading an entire ledger's worth of transaction may currently take several hours to complete.

NOTE: Currently this uses an indy GET_TXN request to get every transaction on the ledger. This is slow and extremely chatty, and should eventually be replaced with a batch message request or catchup solutions; however, these options still need to be implemented in indy-sdk.

## LocalLedger Object

The LocalLedger Python object can download any indy ledger when provided with a pool to connect to and a did on that ledger. It uses a Rocksdb key-value pair database to store the ledger in a local file. Individual transactions can be retrieved in json via their sequence number.

## LedgerQuery Object

The LedgerQuery allows more complex querying of a LocalLedger object. For example, a range of transactions by time and date or sequence number can be queried. All transactions by a certain did may also be retrieved, and every function works with either a LocalLedger storage object or a dictionary of transactions.

## Example

An example file is provided which demonstrates some of the capabilities of the LocalLedger and LedgerReader objects.

To run: 

``` python3 example.py [pool to connect to] [wallet] [wallet key] [did]```

To use, you must have a pool, wallet, and did set up for the ledger you are trying to connect to. Additional instructions to run are found in example.py.

Rocksdb is used to store the ledger locally, just as it is stored on a node.

This is, in a way, a preliminary version of an unprivileged observer node. It could eventually be added to indy-node.
