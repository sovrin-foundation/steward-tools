This is the simple console script for distribution of tokens.

## Usage

To run the token-distribution script you must have the following dependencies installed:
- [indy-sdk](https://github.com/hyperledger/indy-sdk)
- [libsovtoken](https://github.com/sovrin-foundation/libsovtoken)
- python3
- pip3 packages: python3-indy

Run with this command:

``` python3 token-distribution.py [action] [--dataFile=/path] [--emailInfoFile=/path]```

## Workflow
1. Prepare the data

    Starting with a spreadsheet exported as a CSV containing the following data:
    * The first row:
        * Payment address that payments will be taken from
        * Wallet Name
        * Wallet Location
    * The remaining rows of the spreadsheet:
        * Legal name of recipient
        * Number of tokens to be transferred
        * Payment address
        * Email address for notification

    A text file containing the following data:
    * The text of an email to be sent to users who receive tokens
    * Connection information for sending the email

    Note:  the text file containing information required only on the last step.

1. Prepare payment inputs and outputs for building Payment transaction.

    * On a machine with pool access run a script (with `prepare` action) that accepts the spreadsheet as input (`--dataFile` parameter).
    * For each target row in the spreadsheet, a payment output with the specified number of tokens will be prepared.
    * The list of the names and number of tokens for each payment output will be displayed to the user for confirmation.
    * Upon receiving confirmation, the script will ask about a path to Pool Genesis Transactions to connect to Pool to get sources for doing the payment.
    * Prepared data will be stored as a zip file by a user-supplied path (which will be on a USB thumb drive).
    * The exported file will contain all the information required by the next actions.

    Example: `python3 token-distribution.py prepare --dataFile=/path/to/prepared/csv/file.csv`

1. Build Payment transaction and Sign transaction according to data received after `prepare` action.

    * On a machine without network access, but which has wallet access with the signing keys
    run a script (with `build` action) that accepts zip file received after `prepare` action as input (`--dataFile` parameter).
    * The list of the names and number of tokens for each payment output will be displayed to the user for confirmation.
    * Upon receiving confirmation, the script will ask about a key for tha Wallet (this password is never stored), build and sign payment transaction.
    * Transaction and additional data will be stored as a zip file by a user-supplied path (which will be on a USB thumb drive).
    * The exported file will contain all the information required by the next action.

    Example: `python3 token-distribution.py build --dataFile=/path/to/previous/step/zip/file.zip`


1. Publish

    * On a machine with pool access run a script (with `send` action)  that accepts zip file received after `build` action as input (`--dataFile` parameter).
    * Pass `--emailInfoFile` parameter to point on JSON file containing the information for sending the notification email to token recipients.
    * The list of the names and number of tokens for each payment output will be displayed to the user for confirmation.
    * Upon receiving confirmation, the script will publish them to the global ledger.
    * For each payment address that receives tokens, an email will be sent notifying the user that they have received X tokens. If no email is listed, then skip this action.

    Example: `python3 token-distribution.py publish --dataFile=/path/to/previous/step/zip/file.zip --emailInfoFile=/path/email-info.json`