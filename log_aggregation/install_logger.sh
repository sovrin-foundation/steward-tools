#! /bin/bash

ssh-keygen -q -f ./logwriter_key -t ed25519 -N ''
alias=$(./findAlias.sh)
username=$(cat logwriter_key.pub | cut -d ' ' -f 3 | cut -d '@' -f 1)
sed -i -e "s/^ruser='logwriter'/ruser='${alias}'/" ./sovrin-log-xfer.sh
sed -i -e "s/ ${username}@/ ${alias}@/" ./logwriter_key.pub
nodeNum=$(./findNodeNum.sh ${alias})
offset=$(($nodeNum + 5))
sed -i -e "s/^1 /${offset} /" sovrin_logger
sudo mv logwriter_key  current_validators node_address_list sovrin-log-xfer.sh /home/indy
sudo chown indy:indy /home/indy/*
sudo chmod 600 /home/indy/logwriter_key
sudo mv sovrin_logger /etc/cron.d
sudo chown -R indy:indy /var/log/indy
sudo chown root:root /etc/cron.d/sovrin_logger
echo 'Please copy this ssh public key (the whole line) and send it to support@sovrin.org:'
echo ''
cat ./logwriter_key.pub
