# Fiat Reconciler

This tool takes a ledger and time range and calculates how much the owner of each DID should be charged for fiat-funded transactions. The results are saved in a file called `billing [timerange].csv`.

As the details for the fiat payment option are still under revision, this method of calculating billing amounts is only a concept and, for the time being, should not be taken seriously.

## Usage

``` python3 fiatReconciler.py [pool to connect to] [wallet] [wallet key] [did] [startTime] [endTime]```

