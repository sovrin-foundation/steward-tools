#!/usr/bin/env python3
"""
Helper functions for using libindy
"""

import asyncio
import indy.error
import json
import sys
from indy import did, ledger, pool, wallet
import logging
import time

## - Functions - ##

log = logging.getLogger('root')
log.setLevel(logging.INFO)

class LoggerWriter(object):
    def __init__(self, writer):
        self._writer = writer
        self._msg = ''

    def write(self, message):
        self._msg = self._msg + message
        while '\n' in self._msg:
            pos = self._msg.find('\n')
            self._writer(self._msg[:pos])
            self._msg = self._msg[pos+1:]

    def flush(self):
        if self._msg != '':
            self._writer(self._msg)
            self._msg = ''

sys.stderr = LoggerWriter(log.warning)


async def create_wallet(name: str, key: str, path: str = None):
    """
    Create a new wallet
    """
    wallet_config = {
        'id': name
    }
    wallet_credentials = {
        'key': key
    }
    if path:
        log.info("Wallet will be created at custom path: {}".format(path))
        wallet_config['storage_config'] = {
            'path': path
        }
    try:
        log.debug("Creating wallet: '{}'".format(name))
        await wallet.create_wallet(
            json.dumps(wallet_config),
            json.dumps(wallet_credentials)
        )
    except indy.error.IndyError as e:
        if e.error_code == 203:
            pass
        else:
            raise


async def get_attrib(pool_handle: int, from_did: str, attrib: str) -> dict:
    """
    Request an attrib from the pool

    Returns a dictionary of the JSON string returned from the ledger
    """
    log.debug("Creating attrib request for did: '{}' attrib: '{}'".format(from_did, attrib))
    attrib_get_request = await ledger.build_get_attrib_request(
        None,
        from_did,
        attrib,
        None,
        None
    )
    log.debug("Submitting get attrib request to ledger")
    res = await ledger.submit_request(
        pool_handle,
        attrib_get_request
    )
    log.debug("Response received, returning results")
    return json.loads(res)

async def get_did_from_wallet(wallet_handle: int, lookup_did: str) -> str:
    """
    Request a DID from a wallet

    Returns a String of the DID if found, else None
    """
    log.debug("Querying wallet for list of dids from wallet handle: {}".format(wallet_handle))
    dids = await did.list_my_dids_with_meta(wallet_handle)
    dids = json.loads(dids)
    log.debug("Searching for did: '{}' in wallet handle: {}".format(lookup_did, wallet_handle))
    for did_e in dids:
        if did_e['did'] == lookup_did:
            log.debug("Found did: '{}' in wallet handle: {}".format(lookup_did, wallet_handle))
            return did_e
    return None

async def create_pool_config(name: str, genesis_path: str) -> None:
    """
    Creates a new pool config named 'name' using genesis file at 'genesis_path'
    """
    pool_config = {
        'genesis_txn': genesis_path
    }
    log.debug("Creating ledger config for pool: '{}' with genesis at: '{}'".format(name, genesis_path))
    await pool.create_pool_ledger_config(
        name,
        json.dumps(pool_config)
    )

async def open_pool(name: str, genesis_path: str = None) -> int:
    """
    Opens a pool configuration identified by 'name', If it doesn't exist, then
    try and create a pool configuration using genesis_path

    Returns an int representing the pool_handle for use elsewhere
    """
    create_pool_config_needed = True
    pools = await pool.list_pools()
    for ple in pools:
        if ple['pool'] == name:
            create_pool_config_needed = False
            log.debug("Found existing pool: '{}'".format(name))
    if create_pool_config_needed:
        log.debug("Existing pool with name: '{}' not found, will create".format(name))
        if not genesis_path:
            log.error('Need to create pool config, but no genesis_path was passed. Run with --bootstrap first.')
            sys.exit(1)
        log.info("Creating initial pool config for pool: '{}' with genesis_path: '{}'".format(name, genesis_path))
        await create_pool_config(name=name, genesis_path=genesis_path)
    await pool.set_protocol_version(2)
    log.debug("Connecting to pool: '{}'".format(name))
    handle = await pool.open_pool_ledger(
        name,
        None
    )
    log.debug("Successfully connected to pool: '{}' with handle: {}".format(name, handle))
    return handle

async def open_wallet(name: str, key: str, path: str = None):
    """
    Opens a wallet identified by 'name', using key 'key'. If the wallet doesn't
    exist, then try and create the wallet. If 'path' is passed then create the
    wallet at that location instead of the default '~/.indy_client'

    Returns an int representing the wallet_handle for use elsewhere
    """
    libindy_log_level = logging.getLogger("indy.libindy").getEffectiveLevel()
    wallet_config = {
        'id': name
    }
    wallet_credentials = {
        'key': key
    }
    if path:
        wallet_config['storage_config'] = {
            'path': path
        }
    #This is needed to prevent the warning from showing up incase the wallet
    #hasn't been created yet. We'll handle it! Geesh!
    logging.getLogger("indy.libindy").setLevel(logging.ERROR)
    try:
        handle = await wallet.open_wallet(
            json.dumps(wallet_config),
            json.dumps(wallet_credentials)
        )
    except indy.error.IndyError as e:
        #204 means wallet doesn't exist
        if e.error_code == 204:
            if not path:
                log.info("Creating initial wallet: {}".format(name))
            logging.getLogger("indy.libindy").setLevel(libindy_log_level)
            await create_wallet(name=name, key=key, path=path)
            handle = await wallet.open_wallet(
                json.dumps(wallet_config),
                json.dumps(wallet_credentials)
            )
        #207 means WalletAccess Failed... probably because of bad wallet key
        elif e.error_code == 207:
            log.error("Failed to open wallet. Bad wallet key?")
            sys.exit(1)
        else:
            raise
    logging.getLogger("indy.libindy").setLevel(libindy_log_level)
    log.debug("Successfully opened wallet: '{}' with handle: {}".format(name, handle))
    return handle

async def store_did(wallet_handle: int, seed: str) -> tuple:
    """
    Stores a DID to the wallet_handle 'wallet_handle', using the seed 'seed'

    Returns a tuple where:
        First element is a String representing the DID stored
        Second element is a String representing the Verkey
    """
    did_json = {
        'seed': seed
    }
    log.debug("Generating and storing DID and VerKey from a seed, to the wallet handle: {}".format(wallet_handle))
    n_did, n_verkey = await did.create_and_store_my_did(wallet_handle, json.dumps(did_json))
    log.debug("Successfully generated and stored DID: '{}' and VerKey: '{}' from seed to wallet handle: {}".format(n_did, n_verkey, wallet_handle))
    return (n_did, n_verkey)

async def set_attrib(pool_handle: int, wallet_handle: int, src_did: str, attrib: str) -> dict:
    """
    Set the attrib 'attrib' to the did 'src_did' found in 'wallet_handle' to
    the pool 'pool_handle'

    Returns a dictionary of the JSON string returned from the ledger
    """
    log.debug("Creating attrib set request for did: '{}' attrib: '{}'".format(src_did, attrib))
    attrib_set_request = await ledger.build_attrib_request(
        submitter_did=src_did,
        target_did=src_did,
        raw=json.dumps(attrib),
        xhash=None,
        enc=None
    )
    log.debug("Submitting set attrib request to ledger")
    res = await ledger.sign_and_submit_request(
        pool_handle,
        wallet_handle,
        src_did,
        attrib_set_request
    )
    log.debug("Response received, returning results")
    return json.loads(res)
