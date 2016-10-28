#!/bin/bash -eu

LOC=/srv/www.stdin.co.uk/htdocs/iot

# Copy data in
cd /home/widget/iot-test
cp ${LOC}/server.xml .

# Do processing (race condition ho ho)
python3 test.py -c mine.cfg

# Copy everything back again
cp metadata.json ${LOC}
cp data.bin ${LOC}
cp data.png ${LOC}
cp server.xml ${LOC}
cp status.html ${LOC}
