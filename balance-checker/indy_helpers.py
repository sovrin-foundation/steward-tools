import json

from indy.error import IndyError, ErrorCode
from indy import ledger, payment, pool
from constants import PAYMENT_METHOD, POOL_NAME, PROTOCOL_VERSION
from utils import run_coroutine, run_array


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


def get_payment_sources(pool_handle, addresses):
    try:
        requests = run_array(
            [payment.build_get_payment_sources_with_from_request(-1, None, payAddress, -1) for payAddress in addresses])

        responses = run_array(
            [ledger.submit_request(pool_handle, list(request.result())[0]) for request in requests[0]])

        results = run_array(
            [payment.parse_get_payment_sources_with_from_response(PAYMENT_METHOD, response.result()) for response in
             responses[0]])

        res = {}

        for result in results[0]:
            sources, next_ = result.result()
            sources = json.loads(sources)

            if len(sources) == 0:
                continue  # TODO!

            address = sources[0]['paymentAddress']

            if next_ != -1:
                get_next_batch_of_payment_sources(sources, pool_handle, address, next_)

            amount = sum(source['amount'] for source in sources)

            res[address] = amount
        return res
    except IndyError as err:
        handle_payment_error(err)


def get_next_batch_of_payment_sources(sources, pool_handle, address, next_):
    request = run_coroutine(payment.build_get_payment_sources_with_from_request(-1, None, address, next_))
    response = run_coroutine(ledger.submit_request(pool_handle, request))
    batch_sources, next_ = run_coroutine(payment.parse_get_payment_sources_with_from_response(PAYMENT_METHOD, response))
    sources.extend(json.loads(batch_sources))
    if next_ != -1:
        get_next_batch_of_payment_sources(sources, pool_handle, address, next_)
    else:
        return sources


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
