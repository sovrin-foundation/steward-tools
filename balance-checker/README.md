This is the simple console script to detect unauthorized transfers from the payment addresses.
The script checks the ledger to ensure that the balance matches the expected values for each payment address listed in an input file.

## Usage

To run the balance-checker script you must have the following dependencies installed:
- [indy-sdk](https://github.com/hyperledger/indy-sdk)
- [libsovtoken](https://github.com/sovrin-foundation/libsovtoken)
- python3
- pip3 packages: python3-indy

Run with this command:

``` python3 balance-checker.py [--dataFile=/path] [--emailInfoFile=/path]```

#### Parameters
* --dataFile - Input .CSV file containing a list of payment addresses with an expected tokens amount. (columns: "Payment Address", "Tokens Amount"). Example:
```
Payment Address,Tokens Amount
pay:sov:t3vet9QjjSn6SpyqYSqc2ct7aWM4zcXKM5ygUaJktXEkTgL31,100
pay:sov:2vEjkFFe9LhVr47f8SY6r77ZXbWVMMKpVCaYvaoKwkoukP2stQ,10
pay:sov:PEMYpH2L8Raob6nysWfCB1KajZygX1AJnaLzHT1eSo8YNxu1d,200
```
* --emailInfoFile - Input .JSON file containing information required for email notifications. Example:
```
{
  "host": "smtp.gmail.com",
  "port": 465,
  "from": "Sovrin@email.com",
  "to": "TargetSovrin@email.com",
  "subject": "Balance Checker"
}
```

### Run cron job
*  on Unix OS with using `crontab` library.
    1) edit the crontab file using the command: `crontab -e`
    2) add a new line `0 0 * * * ./balance-checker.py --dataFile=/path/to/input_data.csv --emailInfoFile=/path/to/email-info.json` - this implies running every day at midnight (* - Minute * - Hour * - Day * - Month * - Day of week).
    3) save the file




