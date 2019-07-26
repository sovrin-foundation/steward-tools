import json
from getpass import getpass

from indy.error import IndyError, ErrorCode
from indy import wallet, ledger, payment, pool
from constants import PAYMENT_METHOD, POOL_NAME, PROTOCOL_VERSION
from utils import run_coroutine, run_array


def open_wallet(wallet_info) -> int:
    wallet_config = {
        'id': wallet_info['walletId'],
        'storage_config': {
            'path': wallet_info['walletPath']
        }
    }

    key = getpass("Enter Key for Wallet \"{}\":   ".format(wallet_config['id']))

    wallet_credentials = {
        'key': key
    }

    try:
        return run_coroutine(wallet.open_wallet(json.dumps(wallet_config), json.dumps(wallet_credentials)))
    except IndyError as err:
        if err.error_code == ErrorCode.WalletNotFoundError:
            raise Exception('Wallet not found')
        if err.error_code == ErrorCode.CommonInvalidStructure:
            raise Exception('Invalid Wallet name has been provided')
        if err.error_code == ErrorCode.WalletAccessFailed:
            raise Exception('Invalid key has been provided')
        raise Exception(err.message)


def close_wallet(wallet_handle):
    try:
        run_coroutine(wallet.close_wallet(wallet_handle))
    except IndyError as err:
        if err.error_code == ErrorCode.WalletInvalidHandle:
            return
        raise Exception(err.message)


def open_pool() -> int:
    genesis_transactions = input("Enter path to Pool Genesis Transactions file:     ")
    config = {'genesis_txn': genesis_transactions}

    try:
        return run_coroutine(create_and_open_pool(config))
    except IndyError as err:
        if err.error_code == ErrorCode.PoolLedgerNotCreatedError:
            raise Exception('Pool not found')
        if err.error_code == ErrorCode.CommonInvalidParam2:
            raise Exception('Invalid Pool name has been provided')
        if err.error_code == ErrorCode.PoolLedgerTimeout:
            raise Exception('Cannot connect to Pool')
        if err.error_code == ErrorCode.CommonIOError:
            raise Exception('Genesis Transactions file not found')
        raise Exception(err.message)


async def create_and_open_pool(config) -> int:
    await pool.set_protocol_version(PROTOCOL_VERSION)

    try:
        await pool.create_pool_ledger_config(POOL_NAME, json.dumps(config))
    except IndyError as err:
        if err.error_code != ErrorCode.PoolLedgerConfigAlreadyExistsError:
            raise err

    return await pool.open_pool_ledger(POOL_NAME, None)


def close_pool(pool_handle):
    try:
        run_coroutine(close_and_delete_pool(pool_handle))
    except IndyError as err:
        raise Exception(err.message)


async def close_and_delete_pool(pool_handle):
    await pool.close_pool_ledger(pool_handle)
    await pool.delete_pool_ledger_config(POOL_NAME)


def send_transaction(pool_handle: int, transaction: str) -> str:
    try:
        response = json.loads(
            run_coroutine(ledger.submit_request(pool_handle, transaction)))

        if response['op'] != 'REPLY':
            raise Exception(response['reason'])

        return json.dumps(response)
    except IndyError as err:
        if err.error_code == ErrorCode.CommonInvalidStructure:
            raise Exception('Invalid Transaction')
        if err.error_code == ErrorCode.PoolLedgerTimeout:
            raise Exception('Cannot get response from Ledger')
        raise Exception(err.message)


def get_payment_sources(pool_handle: int, payment_address: str):
    try:
        # wallet handle and submitter did can be omitted
        get_payment_sources_request, _ = run_coroutine(
            payment.build_get_payment_sources_request(-1, None, payment_address))

        get_payment_sources_response = send_transaction(pool_handle, get_payment_sources_request)

        payment_sources = run_coroutine(
            payment.parse_get_payment_sources_response(PAYMENT_METHOD, get_payment_sources_response))
        return json.loads(payment_sources)
    except IndyError as err:
        handle_payment_error(err)


def verify_payment_on_ledger(pool_handle, receipts):
    try:
        requests = run_array(
            [payment.build_verify_payment_req(-1, None, receipt) for receipt in receipts])

        responses = run_array(
            [ledger.submit_request(pool_handle, list(request.result())[0]) for request in requests[0]])

        results = run_array(
            [payment.parse_verify_payment_response(PAYMENT_METHOD, response.result()) for response in responses[0]])

        for receipt in [result.result() for result in results[0]]:
            if len(json.loads(receipt)['sources']) == 0:
                raise Exception('Payment failed')
        return
    except IndyError as err:
        handle_payment_error(err)


def build_payment_request(wallet_handle, inputs, outputs):
    try:
        payment_request, _ = run_coroutine(
            payment.build_payment_req(wallet_handle, None, json.dumps(inputs), json.dumps(outputs), None))
        return payment_request
    except IndyError as err:
        handle_payment_error(err)


def parse_payment_response(response):
    try:
        return json.loads(run_coroutine(payment.parse_payment_response(PAYMENT_METHOD, response)))
    except IndyError as err:
        handle_payment_error(err)


def handle_payment_error(err: IndyError):
    if err.error_code == ErrorCode.CommonInvalidStructure:
        raise Exception('Invalid payment address has been provided')
    if err.error_code == ErrorCode.PaymentExtraFundsError:
        raise Exception('Extra funds on inputs')
    if err.error_code == ErrorCode.PaymentInsufficientFundsError:
        raise Exception('Insufficient funds on inputs')
    if err.error_code == ErrorCode.PaymentUnknownMethodError:
        raise Exception('Payment library not found')
    raise Exception(err.message)
