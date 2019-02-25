install_packages.py is a script that will install the Sovrin packages of your choice:
   indy-node
   sovrin
   libindy
   libnullpay
   libvcx
   indy-cli

Prior to running the script you must have the proper repositories configured and pyyaml
installed, as follows:
   $ sudo apt install python3-pip
   $ pip3 install pyyaml
   $ sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 68DB5E88
   $ echo 'deb https://repo.sovrin.org/deb xenial stable' | sudo tee /etc/apt/sources.list.d/Sovrin.list
   $ sudo apt update

The options for the script can be found using the built-in help
   $ ./install_packages.py -h
