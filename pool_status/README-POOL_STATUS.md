pool_status uses indy-sdk calls to query each node in a pool of validators for status. The results are buffered, and a prompt is provided to the user for interactive analysis.

# Setup

### Install indy-sdk:
    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 68DB5E88
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository "deb https://repo.sovrin.org/sdk/deb xenial stable"
    sudo apt-get update
    sudo apt-get install -y libindy
    sudo apt install -y python3-pip
    pip3 install python3-indy

### Get the genesis file for the desired pool(s).
For example, these commands fetch the genesis files for the Sovrin MainNet and TestNet.

    wget https://raw.githubusercontent.com/sovrin-foundation/sovrin/master/sovrin/pool_transactions_live_genesis
    wget https://raw.githubusercontent.com/sovrin-foundation/sovrin/master/sovrin/pool_transactions_sandbox_genesis

### Fetch the pool_status scripts

    wget --no-check-certificate -O steward-tools.zip https://github.com/sovrin-foundation/steward-tools/archive/master.zip
    unzip steward-tools.zip
    cd steward-tools-master/pool_status

# Startup
### First-time use: establishing the pool, wallet and DID
    ./pool_status.py <new_pool_name> <new_wallet_name> <Steward_DID> --didSeed --genesisFile <path_to_genesis_file>
You will be prompted to enter your steward seed and a new string that will be used as an encryption key to the wallet that will be created.
### Thereafter:
    ./pool_status.py <pool_name> <wallet_name> <Steward_DID>
You will be prompted
# Use
Upon startup, the script will contact each validator in the pool. Any validator that does not respond will result in a warning printed to the screen. Other metadata is logged to a local log file.

A prompt is then presented to the user.

    [all]>
To find available commands and syntax, type **help**.

Typically you would set which node(s) you want information on first (default is all). Then you would tell what fields you would like to see. You type in a slash-delimited path in the JSON to the field(s). Autocomplete is implemented to make this easier. Commonly asked-for fields, such as 'primary', have one-word shortcuts. More than one field can be requested in a single query, using commas as delimiters.
