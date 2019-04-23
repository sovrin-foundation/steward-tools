import json
import os

from indy.error import IndyError, ErrorCode
from indy import wallet, did, ledger, payment, pool

from src.utils import run_coroutine, download_remote_file
from src.constants import *


def open_wallet(name: str, key: str) -> int:
    wallet_config = {'id': name}
    wallet_credential = {'key': key}
    try:
        return run_coroutine(wallet.open_wallet(json.dumps(wallet_config), json.dumps(wallet_credential)))
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


def open_pool(config: dict) -> int:
    try:
        return run_coroutine(create_and_open_pool(config))
    except IndyError as err:
        if err.error_code == ErrorCode.PoolLedgerNotCreatedError:
            raise Exception('Pool not found')
        if err.error_code == ErrorCode.CommonInvalidParam2:
            raise Exception('Invalid Pool name has been provided')
        if err.error_code == ErrorCode.PoolLedgerTimeout:
            raise Exception('Cannot connect to Pool')
        raise Exception(err.message)


async def create_and_open_pool(config: dict) -> int:
    await pool.set_protocol_version(2)
    genesis_txn = download_remote_file(config['location_pool_transactions_genesis'])

    try:
        await pool.create_pool_ledger_config(POOL_NAME, json.dumps({'genesis_txn': genesis_txn}))
    except IndyError as err:
        if err.error_code != ErrorCode.PoolLedgerConfigAlreadyExistsError:
            raise err

    os.remove(genesis_txn)
    return await pool.open_pool_ledger(POOL_NAME, None)


def close_pool(pool_handle):
    try:
        run_coroutine(close_and_delete_pool(pool_handle))
    except IndyError as err:
        raise Exception(err.message)


async def close_and_delete_pool(pool_handle):
    await pool.close_pool_ledger(pool_handle)
    await pool.delete_pool_ledger_config(POOL_NAME)


def get_stored_dids(wallet_handle) -> list:
    try:
        dids = run_coroutine(did.list_my_dids_with_meta(wallet_handle))
        return json.loads(dids)
    except IndyError as err:
        raise Exception(err.message)


def sign_transaction(wallet_handle: int, did: str, transaction: str) -> str:
    try:
        return run_coroutine(ledger.multi_sign_request(wallet_handle, did, transaction))
    except IndyError as err:
        if err.error_code == ErrorCode.CommonInvalidStructure:
            raise Exception('Invalid Transaction')
        raise Exception(err.message)


def send_transaction(pool_handle: int, transaction: str):
    try:
        response = json.loads(
            run_coroutine(ledger.submit_request(pool_handle, transaction)))

        if response['op'] != 'REPLY':
            raise Exception(response['reason'])
    except IndyError as err:
        if err.error_code == ErrorCode.CommonInvalidStructure:
            raise Exception('Invalid Transaction')
        if err.error_code == ErrorCode.PoolLedgerTimeout:
            raise Exception('Cannot get response from Ledger')
        raise Exception(err.message)


def build_mint_transaction(wallet_handle: int, payment_address: str, amount: int):
    outputs = [{
        'recipient':
            payment_address if payment_address.startswith(PAYMENT_PREFIX) else PAYMENT_PREFIX + payment_address,
        'amount': amount
    }]

    try:
        return run_coroutine(payment.build_mint_req(wallet_handle, None, json.dumps(outputs), None))
    except IndyError as err:
        if err.error_code == ErrorCode.CommonInvalidStructure:
            raise Exception('Invalid payment address has been provided')
        raise Exception(err.message)
