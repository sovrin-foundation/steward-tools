CONFIG_URL = 'https://raw.githubusercontent.com/sovrin-foundation/steward-tools/master/token-minter/config/config.json'
PAYMENT_LIBRARY = 'sovtoken'
PAYMENT_PREFIX = 'pay:sov:'
POOL_NAME = 'trainingnet'
HELP_TEXT = '''
This utility simplifies the workflow necessary for a group of network trustees to mint on the Sovrin network.

Dependencies: Indy SDK and LibSovToken

This utility includes functionality for:
  * Building a new MINT transaction.
  * Signing an existing MINT transaction.
  * Sending an existing MINT transaction.

Notes:
  * The number of trustees required to sign the mint transaction is defined on the Ledger.
  * Other configuration options are pulled from a shared file so that all trustees use the same values.
'''
