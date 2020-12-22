#!/bin/bash

pushd comms
pipenv lock -r >requirements.txt
popd
pushd updater
pipenv lock -r >requirements.txt
popd
docker-compose build
