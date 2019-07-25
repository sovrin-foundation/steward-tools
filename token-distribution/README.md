This is the simple console script for distribution of tokens.

## Usage

To run the token-distribution script you must have the following dependencies installed:
- [indy-sdk](https://github.com/hyperledger/indy-sdk)
- [libsovtoken](https://github.com/sovrin-foundation/libsovtoken)
- python3
- pip3 packages: python3-indy

Run with this command:

``` python3 token-distribution.py [action] [--dataFile] [--emailInfoFile]```

Actions:
* prepare - prepare payment inputs and outputs for building Payment transaction

    Input:
    * CSV file with following data:
        * The first row of the document contains: the Payment address that payments will be taken from, the Wallet name, and the Wallet location
        * The remaining rows of the spreadsheet contains: Legal name, Number of tokens to be transferred, Email address, and Payment address
    * Pool Genesis Transactions - interactive input during execution

    Output: ZIP archive containing single JSON file with information required by other actions.

    Example: `python3 token-distribution.py prepare --dataFile=/path/input_data.csv`

* build - builds Payment transaction and Sign transaction according to data received after `prepare` action.
It's recommended to perform this action on a different machine without network access.

    Input:
    * ZIP archive received after `prepare` action execution.
    * Wallet Key - interactive input during execution

    Output: ZIP archive containing single JSON file with signed transaction and information required for sending on the ledger.

    Example: `python3 token-distribution.py build --dataFile=/path/result.zip`

* publish - publish Payment transaction on the ledger (do tokens transfer).

    Input:
    * ZIP archive received after `build` action execution.
    * Connection information for sending the email (as `--emailInfoFile=` on script execution)
    * Pool Genesis Transactions - interactive input during execution

    Example: `python3 token-distribution.py build --dataFile=/path/result.zip --emailInfoFile=/path/email-info.json`
