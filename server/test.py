#!/usr/bin/env python3

# TODO needs config file

import argparse
import configparser
import datetime
import json
import os.path
import sys

import xml.etree.ElementTree as ET

from display_renderer import DisplayRenderer
from epd_generator import EPDGenerator
from tide import Tide
from tide_parser import TideParser
from weather import Weather


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)

SLACK = datetime.timedelta(minutes=15)

CLIENT_METADATA = "metadata.json"
SERVER_METADATA = "server.xml"
OUTPUT_EPD = "data.bin"
OUTPUT_PNG = "data.png"

parser = argparse.ArgumentParser(description="Generate new files")
parser.add_argument('-d', '--dir', default='.')
parser.add_argument('-v', '--verbose', action='store_const', const=True, default=False)
parser.add_argument('-t', '--time', help="In the form %%Y-%%m-%%d %%H:%%M")
parser.add_argument('-f', '--force', help='Force a wakeup', action='store_const', const=True, default=False)
parser.add_argument('-c', '--config', help='Configuration', required=True)

args = parser.parse_args()

if not os.path.exists(args.dir):
    print("Non-existent output directory")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(args.config)

client_metadata_path = config.get("General", "ClientMetadata",
                                  fallback=os.path.join(args.dir, CLIENT_METADATA))
server_metadata_path = config.get("General", "ServerMetadata",
                                  fallback=os.path.join(args.dir, SERVER_METADATA))
output_epd_path = config.get("General", "DisplayOutput",
                             fallback=os.path.join(args.dir, OUTPUT_EPD))
output_png_path = config.get("General", "DebugOutput",
                             fallback=os.path.join(args.dir, OUTPUT_PNG))

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

metadata = ET.ElementTree(ET.Element("display"))
if os.path.exists(server_metadata_path):
    metadata = ET.parse(server_metadata_path)
else:
    if args.verbose:
        print("No old metadata to load")

server_node = metadata.find("./server")
if server_node is None:
    server_node = ET.SubElement(metadata.getroot(), "server")

wakeup_node = metadata.find('server/wake')
if wakeup_node is None: # can't use if not?
    wakeup_node = ET.SubElement(server_node, "wake")

default_time = True
next_wake = None
try:
    if "time" in wakeup_node.attrib:
        next_wake = datetime.datetime.strptime(wakeup_node.attrib["time"], "%Y-%m-%dT%H:%M:%S")
        default_time = False
except ValueError:
    print("Failed to read date from wakeup node: '%s'" % wakeup_node.attrib["time"])

if default_time:
    print("Using default wake time")
    next_wake = datetime.datetime(year=1980, month=1, day=1)

# Load tides
tides_node = metadata.find('./server/tides')
if not tides_node:
    print("Creating new tides node")
    tides_node = ET.SubElement(server_node, "tides")

loaded_tides = []
for node in metadata.findall('./server/tides/tide'):
    t = Tide(datetime.datetime.strptime(node.attrib["time"], "%Y-%m-%dT%H:%M:%S"),
             node.attrib["type"],
             float(node.attrib["height"]))
    loaded_tides.append(t)
    if args.verbose:
        print("Loading stored %s" % t)

# Pull the battery value out
last_log_node = metadata.findall('./client/log[last()]')
battery = 0
if len(last_log_node) == 1:
    battery = int(last_log_node[0].attrib["battery"])

if not args.force:
    if current < next_wake:
        if args.verbose:
            print("Waking too early (not yet %s)" % next_wake)
        sys.exit(0)

valid_tides = [tide for tide in loaded_tides if tide.time > day_start]

if len(valid_tides) == 0:
    try:
        if args.verbose:
            print("Fetching new tides")

        # TODO error handle here
        feed_loc = config["Tides"]["Feed"]
        if not feed_loc:
            raise ValueError("No feed configuration, can't fetch tides")
        if feed_loc[0] != '/':
            feed_loc = '/' + feed_loc
        t = TideParser(feed_loc)
        tides_downloaded = t.fetch(args.verbose)
    except ConnectionError:
        print("Failed to fetch tides")
else:
    # print("Using cached data")
    tides_downloaded = loaded_tides

location = (config.getfloat("Geo", "Latitude"),
            config.getfloat("Geo", "Longitude"))

if args.verbose:
    print("Tide times:")
    for t in tides_downloaded:
        print(t)

future_tides = [tide for tide in tides_downloaded if tide.time > current]
today_tides = [tide for tide in tides_downloaded if tide.time > day_start]

if args.verbose:
    print("Future tide times:")
    for t in future_tides:
        print(t)

# Wakeup into tomorrow, although the RSS feed is a bit slower
wake_up_time = datetime.datetime.combine(current.date() + datetime.timedelta(days=1), datetime.time(hour=1, minute=15))

try:
    weather = Weather(config.get("Weather", "ApiKey"))
    weather.fetch_land_observ(config.get("Weather", "LandLocation"))
    weather.fetch_sea_observ(config.get("Weather", "SeaLocation"))
except configparser.NoOptionError as e:
    weather = None
except Exception as e:
    print("Failed to get weather information: ")
    print(e.__doc__)
    print(e.message)
    weather = None

d = None
if len(today_tides) == 0:
    # RSS feed is not correct for today, come back soon
    wake_up_time = current + SLACK # this will be doubled effectively
elif len(future_tides) >= 2:
    # Otherwise wakeup when we need to change the clock
    wake_up_time = future_tides[0].time
    d = DisplayRenderer(future_tides[0], future_tides[1], battery=battery, location=location, weather=weather)
elif len(future_tides) == 1:
    d = DisplayRenderer(future_tides[0], battery=battery, location=location, weather=weather)
    wake_up_time = future_tides[0].time
else:
    # For the sake of something to show we show this morning's, as next morning
    # TODO add a fudge factor of about 40m here?  Means repacking the tuple, and dealing with wrap at midnight
    d = DisplayRenderer(tides_downloaded[0], battery=battery, location=location, weather=weather)

# Remove microseconds
wake_up_time = wake_up_time.replace(microsecond=0)

# TODO save tides
tides_node.clear()

for tide in tides_downloaded:
    tides_node.append(tide.to_xml())

wakeup_node.attrib["time"] = wake_up_time.isoformat()
metadata.write(server_metadata_path, xml_declaration=True)

wake_up_time += SLACK

# We'll only get log messages dated when we did it and when the next one should be
print("Next client wakeup is %s" % wake_up_time)

client_metadata = {"wakeup": wake_up_time.timetuple()}

with open(client_metadata_path, "w") as meta_out:
    json.dump(client_metadata, meta_out)

if d:
    d.render()
    d.save(output_png_path)

    e = EPDGenerator(d.surface_bw)
    e.save(output_epd_path)

    if args.verbose:
        print("Checksum is 0x%x" % e.checksum())
else:
    print("Skipping render, no RSS data")