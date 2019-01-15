#!/usr/bin/env python3

import json
import copy
import argparse
import re
import codecs
import copy
import readline
import getpass
import logging
from logging.handlers import RotatingFileHandler
from helper_functions import *

log_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
logFile = 'poolinfo.log'
my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=1024 * 1024,
                                 backupCount=1, encoding=None, delay=0)
my_handler.setFormatter(log_formatter)
my_handler.setLevel(logging.INFO)
log = logging.getLogger('root')
log.setLevel(logging.INFO)
log.addHandler(my_handler)

pattern1 = re.compile(r'\\u251c[^ ]*')
pattern2 = re.compile(r'\\u25cf[^ ]*')
pattern3 = re.compile(r'\\u2514[^ ]*')

def remove_json_cruft(line):
    line = codecs.escape_decode(line)[0].decode('ascii', 'ignore')
    line = pattern1.sub(r"", line)
    line = pattern2.sub(r"", line)
    line = pattern3.sub(r"", line)
    line = line.replace(r'\/', '/')                        # removes \ on \/
    line = line.replace('\n', '    ')                      # json parser chokes on \n, \t
    line = line.replace('\t', '    ')
    return line

def get_validator_info(pool, wallet, walletKey, did, genesisFile = None, didSeed = None):

    looper = asyncio.get_event_loop()
    looper.run = looper.run_until_complete

    pool_handle = looper.run(open_pool(pool, genesisFile))
    wallet_handle = looper.run(open_wallet(wallet, walletKey))
    if looper.run(get_did_from_wallet(wallet_handle, did)) == None:
        if didSeed == None:
            log.error("DID '{}' does not exist in wallet '{}'. A seed must be provided.".format(wallet, did))
            sys.exit(1)
        else:
            looper.run(store_did(wallet_handle, didSeed))

    v_i_request = looper.run(ledger.build_get_validator_info_request(did))
    vi = looper.run(ledger.sign_and_submit_request(pool_handle,wallet_handle,did,v_i_request))
    jsonStrings = json.loads(vi)
    parsedJson = {}
    for key,value in jsonStrings.items():
        value = remove_json_cruft(value)
        if value == 'timeout':
            print("Warning: Node '{}' is unreachable and will be excluded.".format(key))
        else:
            parsedJson[key] = json.loads(value)['result']['data']
    log.info(json.dumps(parsedJson))
    return parsedJson

def parse_inputs():
    parser = argparse.ArgumentParser(
        description='Get validator-info on a pool, and make an interpretive interactive shell.')
    parser.add_argument('pool', help='The name of the pool to connect to')
    parser.add_argument('wallet', help='The name of the wallet to use')
    parser.add_argument('did', help='DID of steward')
    parser.add_argument('--genesisFile', help='Needed if the pool has not been previously initialized.')
    parser.add_argument('--didSeed', action='store_true', help='Prompt for seed. Use if keys are not yet in your wallet')
    parser.add_argument('--infoFile', help='Get validator info from this JSON file, instead of querying pool. Use of this option means that all other arguments are ignored')
    args = parser.parse_args()

    return args

def add_branch(path, full_branch, destination):
    source_branch = full_branch
    dest_branch = destination
    for step in path:
        try:
            source_branch = source_branch[step]
        except:
            print("Invalid field requested: {}".format(':'.join(path)))
            return
        if step == path[-1]:
            dest_branch[step] = copy.copy(source_branch)
        elif step not in dest_branch.keys():
            dest_branch[step] = {}
        dest_branch = dest_branch[step]

def make_pruned_tree(field_array, node, full_branch):
    destination = {}
    for field in field_array:
        if field == 'transCount':
            add_branch(['Node_info','Metrics','transaction-count'], full_branch, destination)
        elif field == 'reachable':
            add_branch(['Pool_info','Reachable_nodes_count'], full_branch, destination)
            add_branch(['Pool_info','Unreachable_nodes_count'], full_branch, destination)
            add_branch(['Pool_info','Unreachable_nodes'], full_branch, destination)
        elif field == 'version':
            add_branch(['Software','indy-node'], full_branch, destination)
            add_branch(['Software','sovrin'], full_branch, destination)
        elif field == 'primary':
            add_branch(['Node_info','Replicas_status','{}:0'.format(node),'Primary'], full_branch, destination)
        else:
            add_branch(field.split('/'), full_branch, destination)
    return destination

def find_and_print(info, fields, nodes):
    field_array = fields.split(',')
    node_array = nodes.split(',')
    if 'all' in node_array:
        node_array =info.keys()

    pruned = {}
    for node in node_array:
        if 'all' in field_array: # no need to look further if 'all' fields are requested
            pruned[node] = info[node]
        else:
            if info[node] == 'timeout':
                pruned[node] = info[node]
            else:
                pruned[node] = make_pruned_tree(field_array, node, info[node])
    print(json.dumps(pruned, sort_keys=True, indent=4))


def print_help():
    print('The available commands are nodes, show, save, help, and quit.')
    print('First use the nodes command to set for which nodes the stats should be displayed.')
    print('   Example: "> nodes validator01,validator02"')
    print('   "nodes all" will display info for all nodes in the pool. (This is the default)')
    print('Then use show to generate the output. A parameter is required to select which fields to display for each node selected.')
    print('   Options for show include "all", "transCount", "reachable", version and "primary". You can also give an arbitrary field using slashes.')
    print('   Example: "> show transCount"')
    print('   Example: "> show Pool_info/Total_nodes_count"')
    print('   A comma can be used to delimit multiple fields to display')
    print('      Example: "> show transCount,primary"')
    print('To save the data retrieved from the ledger for later offline analysis with this or other tools, use save.')
    print('   Example: > save myfile.json')
    print("")

commands = ['nodes', 'show', 'save', 'help', 'quit']
info = {}
nothing = []

def completer(text, state):
    line = readline.get_line_buffer()
    parts = line.split(' ')
    part_count = len(parts)
    log.debug('Line: "{}", parts: {}'.format(line, part_count))
    if part_count == 1:
         log.debug('part0="{}'.format(parts[0]))
         options = [x for x in commands if x.startswith(text)]
    elif part_count == 2:
        log.debug('part0="{}, part1="{}"'.format(parts[0], parts[1]))
        nodes = list(info.keys())
        if parts[0] == 'show':
            log.debug('c6')
            field = parts[1].split(',')[-1]
            log.debug('Checking for field {}'.format(field))
            subparts = field.split('/')
            treepointer = info[nodes[0]]
            for subpart in subparts[0:-1]:
                log.debug('Looking for completions to {} in {}'.format(subpart, json.dumps(list(treepointer.keys()))))
                try:
                    treepointer = treepointer[subpart]
                except:
                    options = [x for x in nothing if x.startswith(text)]
            if len(subparts) == 1:
                mylist = list(treepointer.keys())
                mylist.append('all')
                mylist.append('transCount')
                mylist.append('reachable')
                mylist.append('version')
                mylist.append('primary')
                options = [x for x in mylist if x.startswith(text)]
            else:
                options = [x for x in treepointer.keys() if x.startswith(text)]
        elif parts[0] == 'nodes':
            log.debug('c7')
            options = [x for x in nodes if x.startswith(text)]
        else:
            log.debug('c8')
            options = [x for x in nothing if x.startswith(text)]
    else:
        log.debug('c9')
        options = [x for x in nothing if x.startswith(text)]
    try:
        log.debug('returning {}'.format(options[state]))
        return options[state]
    except IndexError:
        log.debug('IndexError thrown')
        return None
    log.debug('Exiting normally')


if __name__ == '__main__':
    args=parse_inputs()
    if (args.infoFile):
        print('An input file has been provided. All other arguments will be ignored. Loading file...')
        with open(args.infoFile) as infoStream:
            info = json.load(infoStream)
    else:
        if args.didSeed:
            didSeed = getpass.getpass("DID seed: ")
        else:
            didSeed = None
        walletKey = getpass.getpass("Wallet key: ")
        print('Please be patient while I contact all the nodes in the pool for their status...')
        info = get_validator_info(args.pool, args.wallet, walletKey, args.did, args.genesisFile, didSeed)
    nodes='all'
    action=''
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    while action != 'quit':
        prompt = '[{}]> '.format(nodes)
        result = input(prompt)
        command = result.split()
        if len(command) == 0:
            continue
        action = command[0]
        if action == 'nodes':
            if len(command) == 2:
                valid_nodes = True
                if command[1] == 'all':
                    nodes = 'all'
                for node in command[1].split(','):
                    if node not in info.keys():
                        print("Unrecognized node '{}'".format(node))
                        valid_nodes = False
                        break
                if valid_nodes:
                    nodes = command[1]
            else:
                print('Input error: "nodes" command requires one argument')
        elif action == 'show':
            if len(command) == 2:
                find_and_print(info, command[1], nodes)
            else:
                print('Input error: "show" command requires one argument')
        elif action == 'save':
            if len(command) == 2:
                with open(command[1], 'w') as infoStream:
                    json.dump(info, infoStream)
            else:
                print('Input error: "save" command requires one argument')
        elif action == 'help':
            print_help()
        elif action == 'quit':
            pass
        else:
            print("Invalid instruction: {}".format(result))
            print_help()
