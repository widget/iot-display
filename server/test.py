#!/usr/bin/env python3

import argparse
import configparser
import datetime
import json
import os.path
import rrdtool
import pytz
import sys
import logging

import xml.etree.ElementTree as ET


from display_renderer import DisplayRenderer
from epd_generator import EPDGenerator
from tide import Tide
from tide_parser import TideParser
from weather import Weather


def generate_status_page(metadata_supplied, wake_up_time, status_path):
    try:
        with open(status_path, "w") as statusfile:
            statusfile.write("<html><head>Current status</head><body>")
            statusfile.write("<p>Next wakeup due at %s</p>" % wake_up_time.isoformat())

            statusfile.write("<p>Last events:</p><ol>")

            events = metadata_supplied.findall('./client/log')

            for ev in events[:-6:-1]:  # iterate back over the last five
                statusfile.write("""<li>{time}: {reason} - {battery}%</li>""".format(time=ev.attrib["time"],
                                                                                     reason=ev.attrib["reset"],
                                                                                     battery=ev.attrib["battery"]))
            statusfile.write("</ol><img src='graph.png' /></body></html>")
        # rrdtool.graph("graph.png",
        #               "--start", "-2d",
        #               "DEF:b=%s:battery:LAST" % rrd_path,
        #               "DEF:t=%s:temperature:LAST" % rrd_path,
        #               "LINE:b#FF0000:Battery",
        #               "LINE:t#0000FF:Temperature")
    except (IOError, KeyError):
        pass


def print_time(dt):
    """
    Kept forgetting the strftime format I wanted, save it here
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


class DateTimeEncoder(json.JSONEncoder):
    """
    JSON encoder that overloads the datetime format to output as a string
    """
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


SLACK = datetime.timedelta(minutes=15)

CLIENT_METADATA = "metadata.json"
SERVER_METADATA = "server.xml"
SERVER_STATUS = "status.html"
OUTPUT_EPD = "data.bin"
OUTPUT_PNG = "data.png"
RRD_PATH = "info.rrd"

london = pytz.timezone("Europe/London")
gmt = pytz.timezone("GMT")


parser = argparse.ArgumentParser(description="Generate new files")
parser.add_argument('-d', '--dir', default='.')
parser.add_argument('-v', '--verbose', action='store_const', const=True, default=False)
parser.add_argument('-t', '--time', help="In the form %%Y-%%m-%%d %%H:%%M")
parser.add_argument('-f', '--force', help='Force a wakeup', action='store_const', const=True, default=False)
parser.add_argument('-c', '--config', help='Configuration', required=True)
parser.add_argument('--min', help="Ensure wake-ups at least min time from now", type=int, default=-1)

args = parser.parse_args()

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                    level=logging.DEBUG if args.verbose else logging.INFO)

if not os.path.exists(args.dir):
    print("Non-existent output directory")
    sys.exit(1)
else:
    logging.debug("Using " + args.dir)

config = configparser.ConfigParser()
config.read(args.config)

client_metadata_path = config.get("General", "ClientMetadata",
                                  fallback=os.path.join(args.dir, CLIENT_METADATA))
server_metadata_path = config.get("General", "ServerMetadata",
                                  fallback=os.path.join(args.dir, SERVER_METADATA))
server_status_path = config.get("General", "ServerStatus",
                                fallback=os.path.join(args.dir, SERVER_STATUS))
output_epd_path = config.get("General", "DisplayOutput",
                             fallback=os.path.join(args.dir, OUTPUT_EPD))
output_png_path = config.get("General", "DebugOutput",
                             fallback=os.path.join(args.dir, OUTPUT_PNG))
rrd_path = config.get("General", "RoundRobin",
                             fallback=os.path.join(args.dir, RRD_PATH))

# Filter tides
if not args.time:
    current_local = datetime.datetime.now()
else:
    try:
        current_local = datetime.datetime.strptime(args.time, "%Y-%m-%d %H:%M")
    except ValueError:
        current_local = datetime.datetime.strptime(args.time, "%H:%M")
        current_local = datetime.datetime.combine(datetime.date.today(),
                                                  current_local.time())
        logging.info("Hard-coding time to %s", current_local)

current_local = london.localize(current_local)
day_start = london.localize(datetime.datetime.combine(current_local.today(), datetime.time(0)))

metadata = ET.ElementTree(ET.Element("display"))
if os.path.exists(server_metadata_path):
    metadata = ET.parse(server_metadata_path)
else:
    logging.debug("No old metadata to load")

server_node = metadata.find("./server")
if server_node is None:
    server_node = ET.SubElement(metadata.getroot(), "server")

wakeup_node = metadata.find('server/wake')
if wakeup_node is None:  # can't use if not?
    wakeup_node = ET.SubElement(server_node, "wake")

default_time = True
next_wake = None
try:
    if "time" in wakeup_node.attrib:
        timeval = wakeup_node.attrib["time"]
        if '.' in timeval:
            timeval = timeval.split('.')[0]
        next_wake = london.localize(datetime.datetime.strptime(timeval, "%Y-%m-%dT%H:%M:%S"))
        default_time = False
except ValueError:
    logging.error("Failed to read date from wakeup node: '%s'", wakeup_node.attrib["time"])

if default_time:
    logging.info("Using default wake time")
    next_wake = london.localize(datetime.datetime(year=1980, month=1, day=1))

# Load tides
tides_node = metadata.find('./server/tides')
if not tides_node:
    logging.info("Creating new tides node")
    tides_node = ET.SubElement(server_node, "tides")

loaded_tides = []
for node in metadata.findall('./server/tides/tide'):
    t = Tide(gmt.localize(datetime.datetime.strptime(node.attrib["time"], "%Y-%m-%dT%H:%M:%S")),
             node.attrib["type"],
             float(node.attrib["height"]))
    loaded_tides.append(t)
    logging.debug("Loading stored %s", t)

# Pull the last uploaded values out and log to rrdtool
last_log_node = metadata.findall('./client/log[last()]')
battery = 0
if len(last_log_node) == 1:
    try:
        battery = int(last_log_node[0].attrib["battery"])
        temp = int(last_log_node[0].attrib["screen"])
        try:
            if not os.path.exists(rrd_path):
                logging.info("Creating RRD at ", rrd_path)
                rrdtool.create(rrd_path, "--start", "now",
                               "--step", "10m",
                               "DS:battery:GAUGE:1h:0:100",
                               "DS:temperature:GAUGE:1h:0:100",
                               "RRA:AVERAGE:0.5:10m:3M",
                               "RRA:LAST:0.5:10m:3M")
            rrdtool.update(rrd_path, "N:%s:%s" %(battery, temp))
            logging.debug("Updated RRD %s", rrd_path)
        except rrdtool.OperationalError:
            logging.exception("Couldn't update RRD %s", rrd_path)
    except KeyError:
        logging.exception("Couldn't get data to store in RRD")

if not args.force:
    if current_local < (next_wake-SLACK):
        logging.debug("Waking too early (not yet %s)", (next_wake-SLACK))
        sys.exit(0)

valid_tides = [tide for tide in loaded_tides if tide.time > day_start]
tides_downloaded = []
if len(valid_tides) < 7:
    try:
        logging.debug("Fetching new tides")

        # TODO error handle here
        feed_loc = config["Tides"]["Feed"]
        if not feed_loc:
            raise ValueError("No feed configuration, can't fetch tides")
        t = TideParser(feed_loc)
        tides_downloaded = t.fetch(args.verbose)
    except ConnectionError:
        logging.error("Failed to fetch tides")
else:
    # print("Using cached data")
    tides_downloaded = loaded_tides

location = (config.getfloat("Geo", "Latitude"),
            config.getfloat("Geo", "Longitude"))

if args.verbose:
    logging.debug("Tide times:")
    for t in tides_downloaded:
        logging.debug(t)

if len(tides_downloaded) == 0:
    # TODO handle error
    pass

future_tides = [tide for tide in tides_downloaded if tide.time > current_local]
today_tides = [tide for tide in tides_downloaded if tide.time > day_start]

if args.verbose:
    logging.debug("Future tide times:")
    for t in future_tides:
        logging.debug(t)

# Wakeup into tomorrow, although the RSS feed is a bit slower
wake_up_time_gmt = datetime.datetime.combine(current_local.date() + datetime.timedelta(days=1),
                                             datetime.time(hour=1, minute=15))
wake_up_time_gmt = gmt.localize(wake_up_time_gmt)

try:
    weather = Weather(config.get("Weather", "ApiKey"))
    weather.fetch_land_observ(config.get("Weather", "LandLocation"))
    weather.fetch_sea_observ(config.get("Weather", "SeaLocation"))
except configparser.NoOptionError as e:
    weather = None
except Exception as e:
    logging.exception("Failed to fetch weather information")
    weather = None

d = None
if len(future_tides) >= 2:
    # Otherwise wakeup when we need to change the clock
    wake_up_time_gmt = future_tides[0].time  # GMT! not astimezone(london)
    d = DisplayRenderer(future_tides[0], future_tides[1],
                        battery=battery, location=location, weather=weather, tz=london)
elif len(future_tides) == 1:
    d = DisplayRenderer(future_tides[0],
                        battery=battery, location=location, weather=weather, tz=london)
    wake_up_time_gmt = future_tides[0].time  # GMT! not astimezone(london)
else:
    # For the sake of something to show we show this morning's, as next morning
    d = DisplayRenderer(today_tides[0],
                        battery=battery, location=location, weather=weather)

tides_node.clear()

for tide in tides_downloaded:
    tides_node.append(tide.to_xml())

# if args.min != -1:
#     # OVERRIDE TO NO MORE THAN FOUR HOURS
#     max_sleep = datetime.timedelta(minutes=args.min)
#     if wake_up_time_gmt > (current_local + max_sleep):
#         logging.info("Original wakeup of %s", print_time(wake_up_time_gmt))
#
#         wake_up_time_gmt = current_local + max_sleep
#         logging.info("Now %s (%d min)", (print_time(wake_up_time_gmt), args.min))

# Now the time for the client to wakeup
wake_up_time_gmt += SLACK

# Remove microseconds
wake_up_time_gmt = wake_up_time_gmt.replace(microsecond=0)

# isoformat puts out tz info in the wrong format to be able to bloody load it again
wut = wake_up_time_gmt.isoformat().split('+')[0]
wakeup_node.attrib["time"] = wut

# Save this in the log, so we can compare
client_node = metadata.find('./client')

if client_node:
    if not metadata.findall("./client/requested[@time='%s']" % wut):
        wakeup_log = ET.SubElement(client_node, "requested")  # as in when the client should have come in
        wakeup_log.attrib["time"] = wut

metadata.write(server_metadata_path, xml_declaration=True)

logging.debug("Next client wakeup is %s", wake_up_time_gmt)

client_metadata = {"wakeup": wake_up_time_gmt.timetuple()}

with open(client_metadata_path, "w") as meta_out:
    json.dump(client_metadata, meta_out)

# Actually save the pic
if d:
    d.render()
    d.save(output_png_path)

    e = EPDGenerator(d.surface_bw)
    e.save(output_epd_path)

else:
    logging.info("Skipping render, no RSS data")

