#!/bin/bash

# find which entry in the ledger this node is
findNodeNum() {
#inputs: $1 = node alias

    counter=0
    nodeIndex='None'
    regex='^([^,]*),([0-9\.]*),([0-9]*)$'
    nodeArray=$(./current_validators --writeJson | ./node_address_list)
    for node in $nodeArray ; do
        node=$(/bin/echo $node | /usr/bin/tr -d '\r')
        if [[ $node != 'alias,address,port' ]]
        then
            if [[ $node =~ $regex ]]
            then
                alias="${BASH_REMATCH[1]}"
                if [[ $alias == $1 ]]; then
                    nodeIndex=$counter
                    break
                else
                    counter=$((counter+1))
                    continue
                fi
            else
                >&2 /bin/echo "WARNING: Unrecognized line ${node} in ${1}. Expected '<alias>,<ip_address>,<port>'."
            fi
        fi
    done
    if [[ -z "$nodeIndex" ]]; then
         >&2 /bin/echo "WARNING: Node ${1} not found in ledger"
         randomNumber=$RANDOM
         nodeIndex=$((randomNumber %= 30))
    fi
}


# ------------- MAIN ---------------
findNodeNum $1
/bin/echo $nodeIndex
