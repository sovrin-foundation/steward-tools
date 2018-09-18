#!/bin/bash

network=$(python3 -c 'import sys; sys.path.append("/etc/indy"); import indy_config; print(indy_config.NETWORK_NAME)')
ruser="logwriter"
rpkey="/home/indy/logwriter_key"
rhost="18.217.23.64"
ldir="/var/log/indy/${network}/"
aggdir="${ldir}aggregator/"
maxLogSize=$(expr 1024 \* 1024)

# File rotation function
FileRotate () {
  myfile="${aggdir}${1}"
  CNT=24
  echo "Files to rotate: ${myfile}*"
  let P_CNT=CNT-1

  # Rename logs .1 through .$CNT
  while [[ $CNT -ne 1 ]] ; do
    if [ -f ${myfile}.${P_CNT} ] ; then
      mv -f ${myfile}.${P_CNT} ${myfile}.${CNT}
    fi
    let CNT=CNT-1
    let P_CNT=P_CNT-1
  done
 
  # Rename current file to .1
  if [ -f ${myfile} ] ; then
    mv ${myfile} ${myfile}.1
  fi

  # if this is being run as a cron and a log file is written, rotate that too.
  if [ -f '/home/indy/sovrin-log-xfer.log' ]; then
    file_size=$(du -b /home/indy/sovrin-log-xfer.log | tr -s '\t' ' ' | cut -d' ' -f1)
    echo "log file found of size $file_size"
    if [ $file_size -gt $maxLogSize ]; then 
      mv -f '/home/indy/sovrin-log-xfer.log' '/home/indy/sovrin-log-xfer.log.1'
    fi
  fi
}

# given an ip address and a port, return the round-trip connect time
connectTime() {
#inputs: $1 = IP address of remote server, $2 = port on remote server

    timeResp=$((time nc -v -z -w 1 $1 $2 ) 2>&1)

    regex='^Connection.*succeeded!'
    if [[ "$timeResp" =~ $regex ]]
    then
        regex='real[[:blank:]]0m([0-9\.]+)s'
        if [[ "$timeResp" =~ $regex ]]
        then
            seconds="${BASH_REMATCH[1]}"
            echo "$seconds"
        else
            echo "unconnected"
        fi
    else
        echo "unconnected"
    fi
}

# make a file containing connection times for all nodes in a pool
poolConnectTimes() {
#inputs: $1 = file pathname for output
    
    regex='^([^,]*),([0-9\.]*),([0-9]*)$'
    ./current_validators --writeJson | ./node_address_list | while read -r addLine ; do
        addLine=$(echo $addLine | tr -d "\r")
        if [[ $addLine != "alias,address,port" ]]
        then
            if [[ $addLine =~ $regex ]]
            then
                name="${BASH_REMATCH[1]}"
                address="${BASH_REMATCH[2]}"
                port="${BASH_REMATCH[3]}"
                timeStr=$(connectTime $address $port)
                echo -e "Ping time for ${addLine}: \t${timeStr}" >> $1
            else
                >&2 echo "WARNING: Unrecognized line ${addLine} in ${1}. Expected '<alias>,<ip_address>,<port>'."
            fi
        fi
    done      
}

# ------- MAIN -------
echo "---------------- Starting log aggregation at $(date --iso-8601=seconds) -------------------" 
if [ ! -f "$rpkey" ] ; then
    echo "Missing private key file '$rpkey', aborting"
#    exit 1
fi

mkdir -p ${aggdir}

# make validator-info files
FileRotate ${ruser}_validator_info.txt
/usr/local/bin/validator-info -v > ${aggdir}${ruser}_validator_info.txt

# make ping files
FileRotate ${ruser}_pings.txt
poolConnectTimes ${aggdir}${ruser}_pings.txt

# move files to log aggregator server
rsync -z --progress -a -e "ssh -l ${ruser} -i ${rpkey} -oStrictHostKeyChecking=no" "${ldir}"${ruser}.log* ${rhost}:logs/
rsync -z --progress -a -e "ssh -l ${ruser} -i ${rpkey} -oStrictHostKeyChecking=no" "${aggdir}${ruser}"_validator_info.txt* ${rhost}:status/
rsync -z --progress -a -e "ssh -l ${ruser} -i ${rpkey} -oStrictHostKeyChecking=no" "${aggdir}${ruser}"_pings.txt* ${rhost}:network_health/
echo "---------------- Log sync to remote complete at $(date --iso-8601=seconds) -------------------" 
echo ""
