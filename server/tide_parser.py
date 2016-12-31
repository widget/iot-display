import datetime

from tempfile import NamedTemporaryFile

import pytz
from bs4 import BeautifulSoup
import requests
from tide import Tide


class TideParser(object):
    """
    Parses the UKHO RSS feed to something less crap.  BeautifulSoup4 is depending on
    LXML as RSS is XML, but the HTML in the RSS needs extracting.

    No errors are handled yet, Requests could return ConnectionError or Timeout

    Location ID is pulled manually from the EasyTide system

    """

    def __init__(self, location_id):

        self.url = "http://www.ukho.gov.uk/easytide/EasyTide/ShowPrediction.aspx"

        self.params = {"PortID": location_id,
                       "PredictionLength": "3",
                       "DaylightSavingOffset": "0",
                       "PrinterFriendly": "true",
                       "HeightUnits": "0",
                       "GraphSize": "10"
                       }

    def fetch(self, debug=False):
        sess = requests.Session()
        rsp = sess.get(self.url,params=self.params)

        if rsp.status_code == requests.codes.ok:
            if debug:
                with NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(rsp.content)
                    print("Content written to " + tmp.name)

            feed_doc = BeautifulSoup(rsp.content, "lxml")

            table_list = feed_doc.find_all("table", "HWLWTable")
            year = datetime.datetime.now().year
            SILLY_FORMAT = "%Y, %a %d %b %H:%M"

            # end of year prediction code
            current_month = datetime.datetime.now().month
            # do this on first in new year, when we've started in december
            first_in_next_year = False

            ret = []

            for table in table_list:
                table_date = table.find('th', 'HWLWTableHeaderCell').text
                tide_types = [x.text.strip() for x in table.find_all('th', 'HWLWTableHWLWCellPrintFriendly')]
                times_heights = [x.text.strip() for x in table.find_all('td')]

                midlen = len(times_heights) >> 1
                tide_times = times_heights[0:midlen]
                heights = [float(h[:-2]) for h in times_heights[midlen:]]
                types = ["Low" if x == "LW" else "High" for x in tide_types]
                times = []
                for time in tide_times:
                    if "1 Jan" in table_date and current_month == 12 and not first_in_next_year:
                        # As there's no year information we have to bump forward
                        year += 1
                        first_in_next_year = True
                    times.append(datetime.datetime.strptime(str(year) + ", " + table_date + " " + time, SILLY_FORMAT))

                # Set to GMT, although when it's saved out, this is lost
                gmt = pytz.timezone("GMT")
                times = [gmt.localize(t) for t in times]

                for tide_tuple in zip(times, types, heights):
                    ret.append(Tide(*tide_tuple))

            return ret

        else:
            rsp.raise_for_status()
