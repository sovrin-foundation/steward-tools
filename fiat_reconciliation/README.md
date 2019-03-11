# Fiat Reconciler

This tool takes a ledger and time range and calculates how much the owner of each DID should be charged for fiat-funded transactions. 

The results are saved in a file called `billing [timerange].csv`. This comma separated file has two columns: DID, and total amount to bill for the period.



As the details for the fiat payment option are still under revision, this method of calculating billing amounts is only a concept and, for the time being, should not be taken seriously.

## Usage

To run, you must have indy installed with a pool (ledger network) already configured, a wallet, and a did on that ledger.

``` python3 fiatReconciler.py [pool to connect to] [wallet] [wallet key] [did] [startTime] [endTime]```

Example (used to generate the corresponding file in `examples/`:

``` python3 fiatReconciler.py mainnet wallet_name wallet_password UFSFjGNiain5FQ2m88dijd 01/01/2019 01/20/2019```
