#!/usr/bin/env python3

import argparse
import configparser
import datetime
import json
import logging
import os.path
import sys
from lxml import etree
from typing import TextIO, Optional

import pygal
import pytz
from tzlocal import get_localzone
from pygal.style import LightColorizedStyle

from display_renderer import DisplayRenderer
from epd_generator import EPDGenerator
from tide import Tide
from tide_parser import TideParser
from weather import Weather


def generate_status_page(
    metadata_supplied: etree.ElementTree,
    wake_up_time: datetime.datetime,
    status_path: str,
    output_png_time: Optional[datetime.datetime],
) -> None:
    """
    Creates an HTML status page of what's currently going on:

    * When the next wakeup is due by the display
    * When we last updated the PNG (checking the file timestamp
    * The last five beacons in plain text
    * A graph of responses
    * The current PNG
    """
    try:
        status_file: TextIO

        with open(status_path, "w") as status_file:
            logging.debug("Generating status page at %s", status_path)
            status_file.write(
                """<!doctype html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Current status</title>
    <script type="text/javascript" src="http://kozea.github.com/pygal.js/latest/pygal-tooltips.min.js">
    </script>
</head>
<body>\n"""
            )
            status_file.write(
                "<p>Next wakeup due at %s</p>\n" % wake_up_time.isoformat()
            )

            if output_png_time:
                status_file.write(
                    "<p>Last image update at %s</p>\n" % output_png_time.isoformat()
                )

            status_file.write("<p>Last events:</p>\n<ol>\n")

            events = metadata_supplied.findall("./client/log")

            for ev in events[:-6:-1]:  # iterate back over the last five
                status_file.write(
                    """<li>{time}: {reason} - {battery}%</li>\n""".format(
                        time=ev.attrib["time"],
                        reason=ev.attrib["reset"],
                        battery=ev.attrib["battery"],
                    )
                )

            # draw a graph
            chart = generate_chart(28, events)

            status_file.write(
                "</ol>\n<br /><figure>\n%s</figure>\n"
                % chart.render(disable_xml_declaration=True)
            )

            status_file.write(
                """<img src="data.png" height="300" width="400"/></body>\n</html>
            """
            )

    except (IOError, KeyError):
        logging.exception("Failed to generate status page at %s", status_path)


def generate_chart(days: int, events: etree.ElementTree) -> pygal.DateTimeLine:
    """
    Generate a nice SVG chart in Pygal for the last N days of events
    :param days:
    :param events: The client/log events in the XML
    :return: pygal object for rendering
    """
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    events = [ev for ev in events if "screen" in ev.attrib.keys()]
    dates = [
        datetime.datetime.strptime(pt.attrib["time"].split("+")[0], "%Y-%m-%dT%H:%M:%S")
        for pt in events
    ]
    charge = [int(pt.attrib["battery"]) for pt in events]
    screen_temp = [int(pt.attrib["screen"]) for pt in events]
    charge_pts = [y for y in zip(dates, charge) if y[0] >= cutoff]
    screen_pts = [y for y in zip(dates, screen_temp) if y[0] >= cutoff]

    # Configure the chart style to look nice
    conf = pygal.Config()
    conf.style = LightColorizedStyle
    conf.legend_at_bottom = True
    conf.show_minor_x_labels = True
    conf.x_labels = map(str, range(0, 101, 10))
    conf.tooltip_border_radius = 5
    conf.truncate_label = 11  # Just show the date, not the time
    conf.x_labels = [
        datetime.date.today() - datetime.timedelta(days=x) for x in range(days, -1, -7)
    ]

    # Generate the chart
    chart = pygal.DateTimeLine(conf)
    chart.title = "Client logging"
    chart.add("Battery", charge_pts)
    chart.add("Screen temp", screen_pts)
    chart.range = [0, 100]
    return chart


def print_time(dt: datetime.datetime) -> str:
    """Kept forgetting the strftime format I wanted, save it here"""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that overloads the datetime format to output as a string"""

    def default(self, o):
        """Only change datetimes"""
        if isinstance(o, datetime.datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


# Constants
SLACK = datetime.timedelta(minutes=15)

CLIENT_METADATA = "metadata.json"
SERVER_METADATA = "server.xml"
SERVER_STATUS = "status.html"
OUTPUT_EPD = "data.bin"
OUTPUT_PNG = "data.png"

our_tz = get_localzone()
gmt = pytz.timezone("GMT")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate new files")
    parser.add_argument("-d", "--dir", default=".")
    parser.add_argument(
        "-v", "--verbose", action="store_const", const=True, default=False
    )
    parser.add_argument("-t", "--time", help="In the form %%Y-%%m-%%d %%H:%%M")
    parser.add_argument(
        "-f",
        "--force",
        help="Force a wakeup",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument("-c", "--config", help="Configuration", required=True)
    parser.add_argument(
        "--min", help="Ensure wake-ups at least min time from now", type=int, default=-1
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if not os.path.exists(args.dir):
        logging.fatal("Non-existent output directory")
        sys.exit(1)
    else:
        logging.debug("Using " + args.dir)

    config = configparser.ConfigParser()
    config.read(args.config)

    client_metadata_path = config.get(
        "General", "ClientMetadata", fallback=os.path.join(args.dir, CLIENT_METADATA)
    )
    server_metadata_path = config.get(
        "General", "ServerMetadata", fallback=os.path.join(args.dir, SERVER_METADATA)
    )
    server_status_path = config.get(
        "General", "ServerStatus", fallback=os.path.join(args.dir, SERVER_STATUS)
    )
    output_epd_path = config.get(
        "General", "DisplayOutput", fallback=os.path.join(args.dir, OUTPUT_EPD)
    )
    output_png_path = config.get(
        "General", "DebugOutput", fallback=os.path.join(args.dir, OUTPUT_PNG)
    )

    # Filter tides
    if not args.time:
        current_local = datetime.datetime.now()
    else:
        try:
            current_local = datetime.datetime.strptime(args.time, "%Y-%m-%d %H:%M")
        except ValueError:
            current_local = datetime.datetime.strptime(args.time, "%H:%M")
            current_local = datetime.datetime.combine(
                datetime.date.today(), current_local.time()
            )
            logging.info("Hard-coding time to %s", current_local)

    current_local = our_tz.localize(current_local)
    day_start = our_tz.localize(
        datetime.datetime.combine(current_local.today(), datetime.time(0))
    )

    metadata = etree.ElementTree(etree.Element("display"))
    if os.path.exists(server_metadata_path):
        metadata = etree.parse(server_metadata_path)
    else:
        logging.warning("No old metadata to load")

    server_node = metadata.find("./server")
    if server_node is None:
        server_node = etree.SubElement(metadata.getroot(), "server")

    wakeup_node = metadata.find("server/wake")
    if wakeup_node is None:  # can't use if not?
        wakeup_node = etree.SubElement(server_node, "wake")

    next_wake = None
    try:
        if "time" in wakeup_node.attrib:
            timeval = wakeup_node.attrib["time"]
            if "." in timeval:
                timeval = timeval.split(".")[0]
            next_wake = our_tz.localize(
                datetime.datetime.strptime(timeval, "%Y-%m-%dT%H:%M:%S")
            )
    except ValueError:
        logging.error(
            "Failed to read date from wakeup node: '%s'", wakeup_node.attrib["time"]
        )

    if not next_wake:
        logging.info("Using default wake time")
        next_wake = our_tz.localize(datetime.datetime(year=1980, month=1, day=1))

    # Load tides
    tides_node = metadata.find("./server/tides")
    if not tides_node:
        logging.info("Creating new tides node")
        tides_node = etree.SubElement(server_node, "tides")

    loaded_tides = []
    for node in metadata.findall("./server/tides/tide"):
        t = Tide(
            gmt.localize(
                datetime.datetime.strptime(node.attrib["time"], "%Y-%m-%dT%H:%M:%S")
            ),
            node.attrib["type"],
            float(node.attrib["height"]),
        )
        loaded_tides.append(t)
        logging.debug("Loading stored %s", t)

    # Pull the last battery for putting in the display
    last_log_node = metadata.find("./client/log[last()]")
    battery = 0
    try:
        battery = int(last_log_node.attrib["battery"])
    except AttributeError:
        logging.info("No last battery information to display")

    # Is new data needed yet? (or forced)
    if args.force or current_local >= (next_wake - SLACK):
        valid_tides = [tide for tide in loaded_tides if tide.time > day_start]
        tides_downloaded = []
        if len(valid_tides) < 7:
            try:
                logging.info("Fetching new tides")

                # TODO error handle here
                feed_loc = config["Tides"]["Feed"]
                if not feed_loc:
                    raise ValueError("No feed configuration, can't fetch tides")
                t = TideParser(feed_loc)
                tides_downloaded = t.fetch(args.verbose)
            except ConnectionError:
                logging.error("Failed to fetch tides")
        else:
            logging.debug("Using cached data")
            tides_downloaded = loaded_tides

        location = (
            config.getfloat("Geo", "Latitude"),
            config.getfloat("Geo", "Longitude"),
        )

        if args.verbose:
            logging.debug("Tide times:")
            for t in tides_downloaded:
                logging.debug(t)

        if len(tides_downloaded) == 0:
            # TODO handle error
            logging.warning("No tides remaining")

        future_tides = [tide for tide in tides_downloaded if tide.time > current_local]
        today_tides = [tide for tide in tides_downloaded if tide.time > day_start]

        if args.verbose:
            logging.debug("Future tide times:")
            for t in future_tides:
                logging.debug(t)

        # Wakeup into tomorrow, although the RSS feed is a bit slower
        wake_up_time_gmt = datetime.datetime.combine(
            current_local.date() + datetime.timedelta(days=1),
            datetime.time(hour=1, minute=15),
        )
        wake_up_time_gmt = gmt.localize(wake_up_time_gmt)

        weather = None
        try:
            weather = Weather(config.get("Weather", "ApiKey"))
            weather.fetch_land_observ(config.get("Weather", "LandLocation"))
            weather.fetch_sea_observ(config.get("Weather", "SeaLocation"))
            logging.info("Loaded weather")
        except configparser.NoOptionError as e:
            logging.warning("No weather configured")
            weather = None
        except Exception as e:
            logging.exception("Failed to fetch weather information")

        d = None
        if len(future_tides) >= 2:
            # Otherwise wakeup when we need to change the clock
            wake_up_time_gmt = future_tides[0].time  # GMT! not astimezone(london)
            d = DisplayRenderer(
                future_tides[0],
                future_tides[1],
                battery=battery,
                location=location,
                weather=weather,
                tz=our_tz,
            )
        elif len(future_tides) == 1:
            d = DisplayRenderer(
                future_tides[0],
                battery=battery,
                location=location,
                weather=weather,
                tz=our_tz,
            )
            wake_up_time_gmt = future_tides[0].time  # GMT! not astimezone(london)
        else:
            # For the sake of something to show we show this morning's, as next morning
            d = DisplayRenderer(
                today_tides[0], battery=battery, location=location, weather=weather
            )

        tides_node.clear()

        for tide in tides_downloaded:
            tides_node.append(tide.to_xml())

        # Now the time for the client to wakeup
        wake_up_time_gmt += SLACK

        # Remove microseconds
        wake_up_time_gmt = wake_up_time_gmt.replace(microsecond=0)
        # isoformat puts out tz info in the wrong format to be able to bloody load it again
        wut = wake_up_time_gmt.isoformat().split("+")[0]
        wakeup_node.attrib["time"] = wut

        # Save this in the log, so we can compare
        client_node = metadata.find("./client")

        if client_node:
            if not metadata.findall("./client/requested[@time='%s']" % wut):
                wakeup_log = etree.SubElement(
                    client_node, "requested"
                )  # as in when the client should have come in
                wakeup_log.attrib["time"] = wut

        logging.info("Writing back metadata XML")
        metadata.write(server_metadata_path, xml_declaration=True, encoding="utf-8")

        logging.info("Next client wakeup requested %s", wake_up_time_gmt)

        client_metadata = {"wakeup": wake_up_time_gmt.timetuple()}

        logging.info("Writing client json")
        with open(client_metadata_path, "w") as meta_out:
            json.dump(client_metadata, meta_out)

        # Actually save the pic
        if d:
            logging.info("Creating forecast images")
            d.render()
            d.save(output_png_path)

            e = EPDGenerator(d.surface_bw)
            e.save(output_epd_path)

        else:
            logging.warning("Skipping render, no RSS data")
    else:

        logging.info("Waking too early (not yet %s)", (next_wake - SLACK))
        wake_up_time_gmt = next_wake.astimezone(gmt)

    # Now generate the status page anyway because the client could have connected
    png_create_time = None
    try:
        log_time = png_create_time = datetime.datetime.fromtimestamp(
            os.path.getmtime(output_png_path)
        )
        status_create_time = datetime.datetime.fromtimestamp(
            os.path.getmtime(server_status_path)
        )
        if last_log_node is not None:
            log_time = datetime.datetime.strptime(
                last_log_node.attrib["time"], "%Y-%m-%dT%H:%M:%S"
            )
            logging.info("Last client login was " + str(log_time))
        else:
            logging.info("No beacon yet")
        logging.info("Last PNG change was " + str(png_create_time))
        logging.info("Last status page update was " + str(status_create_time))
        if status_create_time < png_create_time or status_create_time < log_time:
            logging.info("Generating new status page")
            generate_status_page(
                metadata, wake_up_time_gmt, server_status_path, png_create_time
            )
            logging.info("All done")
    except OSError:
        logging.exception("Cannot generate status page, no PNG to check")  #
