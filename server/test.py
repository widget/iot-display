#!/usr/bin/env python3

# TODO needs config file

import argparse
import datetime
import json
import os.path
import sys

import pickle

from display_renderer import DisplayRenderer
from epd_generator import EPDGenerator
from tide_parser import TideParser


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)

SLACK = datetime.timedelta(minutes=15)

CLIENT_METADATA = "metadata.json"
SERVER_METADATA = "server.bin"
OUTPUT_EPD = "data.bin"
OUTPUT_PNG = "data.png"

parser = argparse.ArgumentParser(description="Generate new files")
parser.add_argument('-d', '--dir', default='.')
parser.add_argument('-v', '--verbose', action='store_const', const=True, default=False)
parser.add_argument('-t', '--time', help="In the form %%Y-%%m-%%d %%H:%%M")
parser.add_argument('-f', '--force', help='Force a wakeup', action='store_const', const=True, default=False)

args = parser.parse_args()

if not os.path.exists(args.dir):
    print("Non-existent output directory")
    sys.exit(1)

client_metadata_path = os.path.join(args.dir, CLIENT_METADATA)
server_metadata_path = os.path.join(args.dir, SERVER_METADATA)
output_epd_path = os.path.join(args.dir, OUTPUT_EPD)
output_png_path = os.path.join(args.dir, OUTPUT_PNG)

# Filter tides
if not args.time:
    current = datetime.datetime.now()
else:
    try:
        current = datetime.datetime.strptime(args.time, "%Y-%m-%d %H:%M")
    except ValueError:
        current = datetime.datetime.strptime(args.time, "%H:%M")
        current = datetime.datetime.combine(datetime.date.today(),
                                            current.time())
        print("Hard-coding time to %s" % current)

day_start = datetime.datetime.combine(current.today(), datetime.time(0))

last_metadata = {}
if os.path.exists(server_metadata_path):
    with open(server_metadata_path, 'rb') as data_in:
        last_metadata = pickle.load(data_in)
else:
    if args.verbose:
        print("No old metadata to load")

next_wake = last_metadata.get("wakeup", datetime.datetime(year=1980,month=1,day=1))
if not args.force:
    if current < next_wake:
        if args.verbose:
            print("Waking too early (not yet %s)" % next_wake)
        sys.exit(0)

valid_tides = []
if len(last_metadata.get("tides", [])) > 0:
    valid_tides = [tide for tide in last_metadata["tides"] if tide[0] > day_start]

if len(valid_tides) == 0:
    # print("Fetching new tides")

    # TODO error handle here
    t = TideParser()
    tides_downloaded = t.fetch(args.verbose)
else:
    # print("Using cached data")
    tides_downloaded = last_metadata["tides"]

if args.verbose:
    print("Tide times:")
    for t in tides_downloaded:
        print(repr(t))

future_tides = [tide for tide in tides_downloaded if tide[0] > current]
today_tides = [tide for tide in tides_downloaded if tide[0] > day_start]

if args.verbose:
    print("Future tide times:")
    for t in future_tides:
        print(repr(t))

# Wakeup into tomorrow, although the RSS feed is a bit slower
wake_up_time = datetime.datetime.combine(current.date() + datetime.timedelta(days=1), datetime.time(hour=1, minute=15))

if len(today_tides) == 0:
    # RSS feed is not correct for today, come back soon
    wake_up_time = current + SLACK # this will be doubled effectively
elif len(future_tides) >= 2:
    # Otherwise wakeup when we need to change the clock
    wake_up_time = future_tides[0][0]
    d = DisplayRenderer(future_tides[0], future_tides[1])
elif len(future_tides) == 1:
    d = DisplayRenderer(future_tides[0])
    wake_up_time = future_tides[0][0]
else:
    # For the sake of something to show we show this morning's, as next morning
    # TODO add a fudge factor of about 40m here?  Means repacking the tuple, and dealing with wrap at midnight
    d = DisplayRenderer(tides_downloaded[0])

server_metadata = {"wakeup": wake_up_time,
                   "tides": tides_downloaded}
with open(server_metadata_path, "wb") as meta_out:
    pickle.dump(server_metadata, meta_out)

wake_up_time += SLACK

# We'll only get log messages dated when we did it and when the next one should be
print("Next client wakeup is %s" % wake_up_time)

client_metadata = {"wakeup": wake_up_time.timetuple()}

with open(client_metadata_path, "w") as meta_out:
    json.dump(client_metadata, meta_out)

d.render()
d.save(output_png_path)

e = EPDGenerator(d.surface_bw)
e.save(output_epd_path)

if args.verbose:
    print("Checksum is 0x%x" % e.checksum())
