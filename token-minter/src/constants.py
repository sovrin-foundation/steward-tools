CONFIG_URL = 'https://github.com/Artemkaaas/token-minter/raw/config/config.json'
PAYMENT_LIBRARY = 'sovtoken'
PAYMENT_PREFIX = 'pay:sov:'
POOL_NAME = 'minter_pool'
HELP_TEXT = '''
This is the simple utility for minting tokens based on Indy-Sdk and Libsovtoken libraries.

This utility includes functionality of:
  * Building a new MINT transaction.
  * Signing an existing MINT transaction.
  * Sending an existing MINT transaction.

Note: There is a predefined value on the Ledger specifying the number of TRUSTEEs which must sign MINT transaction before a sending.
'''
