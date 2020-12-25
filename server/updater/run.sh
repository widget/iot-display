#!/bin/bash
#
# Crude script to make our python script a regular event
#
# TODO have the python script just sleep itself, would be more reliable

control_c()
{
  kill -s SIGINT $(jobs -p) # kill the sleep
  exit #$
}

trap control_c INT

echo "Running with args: $*"
while true
do
  python tideclock_generator.py $*
  sleep 600 &
  wait # on the sleep so bash can handle interrupt
done
