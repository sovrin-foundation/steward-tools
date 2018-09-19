#! /bin/bash


    if [[ -d /var/log/indy/live ]]; then
        netname='live'
    elif [[ -d /var/log/indy/sandbox ]]; then
        netname='sandbox'
    else
        >&2 echo "WARNING: There are logs for neither live nor sandbox, so unable to determine node alias."
        exit 1
    fi

    regex="/var/log/indy/${netname}/([^\.]*).log"
    logName=$(/bin/ls /var/log/indy/${netname}/*.log)
    if [[ $logName =~ $regex ]]; then
        alias="${BASH_REMATCH[1]}"
    else
        >&2 echo "WARNING: Unable to find a log file named /var/log/indy/${netname}/<alias>.log, so unable to determine node alias."
    fi

echo $alias
