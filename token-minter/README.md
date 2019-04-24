# Token minter

This is the simple GUI utility for minting tokens based on [Indy-Sdk](https://github.com/hyperledger/indy-sdk) and [Libsovtoken](https://github.com/sovrin-foundation/libsovtoken) libraries.

## Prerequisites

### System Dependencies
* Python3
* python3-tk - `sudo apt-get install -y python3-tk`
* Indy-SDK - https://github.com/hyperledger/indy-sdk#installing-the-sdk
* Libsovtoken - do the same steps as for Libindy but use at the end `sudo apt-get install -y libsovtoken`.

### Data
* Wallet with a DID on that ledger. This can be done using the [Indy-CLI](https://github.com/hyperledger/indy-sdk).

### Run
    `python3 run.py`

## Installation
* Ubuntu
    ```
    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 68DB5E88
    sudo add-apt-repository "deb https://repo.sovrin.org/test/deb xenial token-minter"
    sudo apt-get update
    sudo apt-get install -y token-minter
    ```

* Windows
  * Download `libsovtoken.dll` from https://repo.sovrin.org/test/windows/token-minter/
  * Add path to `libsovtoken.dll` to `PATH` environment variable.
  * [Install Indy](https://github.com/hyperledger/indy-sdk#windows)
  * Download `token-minter.exe` from https://repo.sovrin.org/test/windows/token-minter/
  * Run token-minter.exe
