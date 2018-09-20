#! /bin/bash

/usr/bin/ssh-keygen -q -f ./logwriter_key -t ed25519 -N ''
alias=$(./findAlias.sh)
username=$(/bin/cat logwriter_key.pub | /usr/bin/cut -d ' ' -f 3 | /usr/bin/cut -d '@' -f 1)
/bin/sed -i -e "s/^ruser='logwriter'/ruser='${alias}'/" ./sovrin-log-xfer.sh
/bin/sed -i -e "s/ ${username}@/ ${alias}@/" ./logwriter_key.pub
nodeNum=$(./findNodeNum.sh ${alias})
offset=$(($nodeNum + 5))
/bin/sed -i -e "s/^1 /${offset} /" sovrin_logger
/usr/bin/sudo /bin/mv logwriter_key  current_validators node_address_list sovrin-log-xfer.sh /home/indy
/usr/bin/sudo /bin/chown indy:indy /home/indy/*
/usr/bin/sudo /bin/chmod 600 /home/indy/logwriter_key
/usr/bin/sudo /bin/mv sovrin_logger /etc/cron.d
/usr/bin/sudo /bin/chown -R indy:indy /var/log/indy
/usr/bin/sudo /bin/chown root:root /etc/cron.d/sovrin_logger
/bin/echo 'Please copy this ssh public key (the whole line) and send it to support@sovrin.org:'
/bin/echo ''
/bin/cat ./logwriter_key.pub
