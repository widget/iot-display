#!/bin/bash -eu

rsync -av --exclude data ./ thor.stdin.co.uk:iot2/
