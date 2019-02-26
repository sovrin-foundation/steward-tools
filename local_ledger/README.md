# Local Ledger Tool

This tool allows you to download a copy of a specified ledger to your local machine. It also provides methods for different types of queries on the local copy.

This tool is still being developed and should not be used in production for the time being.

A sample file is provided that downloads the ledger (may take a few hours for now) and then performs simple queries.

To run: 

``` python3 example.py [pool to connect to] [wallet] [wallet key] [did]```

Additional instructions to run are found in example.py.

Rocksdb is used to store the ledger locally, just as it is stored on a node.

This is, in a way, a preliminary version of an unprivileged observer node. It could eventually be added to indy-node.
