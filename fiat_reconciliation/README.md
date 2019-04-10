# Fiat Reconciler

This tool takes a ledger and time range and calculates how much the owner of each DID should be charged for fiat-funded transactions. 

The results are saved in a file called `billing [timerange].csv`. This comma separated file has two columns: DID, and total amount to bill for the period.

As the details for the fiat payment option are still under revision, this method of calculating billing amounts is only a concept and, for the time being, should not be taken seriously.

## Usage

To run the reconciler script alone, you must have the following dependencies installed:
- [indy-sdk](https://github.com/hyperledger/indy-sdk) 
- [rocksdb](https://github.com/facebook/rocksdb/blob/master/INSTALL.md)
- python3
- pip3 packages: python3-indy python-rocksdb  


You must also have a pool (ledger network) already configured, a wallet, and a did on that ledger. This can be done using the indy-cli (part of indy-sdk).

Run with this command:

``` python3 fiatReconciler.py [pool to connect to] [wallet] [wallet key] [did] [startTime] [endTime]```

Example (used to generate the corresponding file in `examples/`:

``` python3 fiatReconciler.py mainnet wallet_name wallet_password UFSFjGNiain5FQ2m88dijd 01/01/2019 02/01/2019```

*Note:* This does not work on macOS, as one of indy's dependencies, ZeroMQ, has a bug. ZeroMQ will eventually be replaced, which will resolve this.

While `webserver.py` and `index.html` are stored here, they are run internally by Sovrin, and instructions are not provided to run these.
