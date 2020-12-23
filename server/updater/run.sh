#!/bin/bash
#
# Crude script to make our python script a regular event

control_c()
{
  kill -SIGINT $(jobs -p) # kill the sleep
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
