#! /bin/bash


    if [[ -d /var/log/indy/live ]]; then
        regex='/var/log/indy/live/([^\.]*).log'
        logName=$(/bin/ls /var/log/indy/live/*.log)
        if [[ $logName =~ $regex ]]; then
            alias="${BASH_REMATCH[1]}"
        else
            >&2 echo "WARNING: Unable to find a log file named /var/log/indy/live/<alias>.log, so unable to determine node alias."
        fi
    elif [[ -d /var/log/indy/sandbox ]]; then
        regex='/var/log/indy/sandbox/([^\.]*).log'
        logName=$(/bin/ls /var/log/indy/sandbox/*.log)
        if [[ $logName =~ $regex ]]; then
            alias="${BASH_REMATCH[1]}"
        else
            >&2 echo "WARNING: Unable to find a log file named /var/log/indy/sandbox/<alias>.log, so unable to determine node alias."
        fi
    else
        >&2 echo "WARNING: There are logs for neither live nor sandbox, so unable to determine node alias."

    fi

echo $alias
