#!/usr/bin/python3

import argparse
import os

from indy_common.txn_util import getTxnOrderedFields

from ledger.genesis_txn.genesis_txn_file_util import create_genesis_txn_init_ledger
from plenum.common.member.member import Member
from plenum.common.member.steward import Steward

from plenum.common.constants import TARGET_NYM, TXN_TYPE, DATA, ALIAS, BLS_KEY, \
    TXN_ID, NODE, CLIENT_IP, CLIENT_PORT, NODE_IP, NODE_PORT, CLIENT_STACK_SUFFIX, NYM, \
    STEWARD, ROLE, SERVICES, VALIDATOR, TRUSTEE, IDENTIFIER, VERKEY

import sys
import csv


def parse_trustees(trusteeFile):
   trustees = []
   with open(trusteeFile, newline='') as csvfile:
      reader = csv.DictReader(csvfile, delimiter=',')
      for row in reader:
         trustees.append({'name':row['Trustee name'], 'nym':row['Trustee DID'], 'verkey':row['Trustee verkey']})
   return trustees
         

def parse_stewards(stewardFile, trusteeDID):
   stewards = []
   nodes = []
   with open(stewardFile, newline='') as csvfile:
      reader = csv.DictReader(csvfile, delimiter=',')
      for row in reader:
         stewards.append({'nym':row['Steward DID'], 'verkey':row['Steward verkey'], 'auth_did':trusteeDID})
         nodes.append({'auth_did':row['Steward DID'], 'alias':row['Validator alias'], 'node_address':row['Node IP address'], 
                       'node_port':row['Node port'], 'client_address':row['Client IP address'], 
                       'client_port':row['Client port'], 'verkey':row['Validator verkey'], 
                       'bls_key':row['Validator BLS key'], 'bls_pop':row['Validator BLS POP']})
   return stewards, nodes


def open_ledger(pathname):
   baseDir = os.path.dirname(pathname)
   if baseDir == '':
      baseDir = './'
   else:
      baseDir = baseDir + '/'
   txnFile = os.path.basename(pathname)
   ledger = create_genesis_txn_init_ledger(baseDir, txnFile)
   ledger.reset()
   return ledger


def make_pool_genesis(pool_pathname, node_defs):
   pool_ledger = open_ledger(pool_pathname)   

   seq_no = 1
   for node_def in node_defs:
      txn = Steward.node_txn(node_def['auth_did'], node_def['alias'], node_def['verkey'],
                                  node_def['node_address'], node_def['node_port'], node_def['client_port'], 
                                  client_ip=node_def['client_address'], blskey=node_def['bls_key'],
                                  seq_no=seq_no, protocol_version=None, bls_key_proof=node_def['bls_pop'])
      pool_ledger.add(txn)
      seq_no += 1

   pool_ledger.stop()


def make_domain_genesis(domain_pathname, trustee_defs, steward_defs):
   domain_ledger = open_ledger(domain_pathname)
   
   seq_no = 1
   for trustee_def in trustee_defs:
      txn = Member.nym_txn(trustee_def['nym'], name=trustee_def['name'], verkey=trustee_def['verkey'], role=TRUSTEE,
                           seq_no=seq_no,
                           protocol_version=None)
      domain_ledger.add(txn)
      seq_no += 1   

   for steward_def in steward_defs:
      txn = Member.nym_txn(steward_def['nym'], verkey=steward_def['verkey'], role=STEWARD, 
                           creator=trustee_def['nym'],
                           seq_no=seq_no,
                           protocol_version=None)
      domain_ledger.add(txn)
      seq_no += 1
   
   domain_ledger.stop()


# --- MAIN ---

parser = argparse.ArgumentParser(description = 'Uses .csv files as inputs for trustee and steward info, and produces genesis files.')
parser.add_argument('--pool', help='[OUTPUT] pool transactions pathname.', default='./pool_transactions')
parser.add_argument('--domain', help='[OUTPUT] domain transactions pathname.', default='./domain_transactions')
required = parser.add_argument_group('required arguements')
required.add_argument('--trustees', help="[INPUT] .csv with headers: 'Trustee name', 'Trustee DID', 'Trustee verkey'", required=True)
required.add_argument('--stewards', help="[INPUT] .csv with headers: 'Steward DID', 'Steward verkey', 'Validator alias', 'Node IP address','Node port', 'Client IP address', 'Client port', 'Validator verkey', 'Validator BLS key', 'Validator BLS POP'", required=True)

args = parser.parse_args()

trustee_defs = parse_trustees(args.trustees)
steward_defs, node_defs = parse_stewards(args.stewards, trustee_defs[0]["nym"])   # The first trustee 'onboards' all stewards

make_pool_genesis(args.pool, node_defs)
make_domain_genesis(args.domain, trustee_defs, steward_defs)

