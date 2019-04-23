#!/bin/bash

set -e
set -x

if [ "$1" = "--help" ] ; then
  echo "Usage: <version>"
  return
fi

version="$1"

pyinstaller --onefile \
    --name token-minter \
    --clean \
    ../src/main.py

fpm --input-type "dir" \
    --output-type "deb" \
    --verbose \
    --architecture "amd64" \
    --name token-minter \
    --description "This is the simple GUI utility for minting tokens based on Indy-SDL and Libsovtoken libraries" \
    --license "MIT/Apache-2.0" \
    --version $version \
    --depends "libindy = 1.8.2" \
    --depends "libsovtoken = 0.9.7" \
    --depends "python3-tk" \
    ./dist/token-minter=/usr/bin/token-minter

rm -rf build/ dist/ token-minter.spec