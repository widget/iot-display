#!/bin/bash -eu

pushd comms
pipenv requirements >requirements.txt
popd
pushd updater
pipenv requirements >requirements.txt
popd
docker compose build
