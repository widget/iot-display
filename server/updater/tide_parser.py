import datetime
import logging
from tempfile import NamedTemporaryFile

import pytz
import requests
from tide import Tide
from tzlocal import get_localzone


class TideParser(object):
    """
    Parses the UKHO print feed JSON endpoint.  This will probably break.

    No errors are handled yet, Requests could return ConnectionError or Timeout

    Location ID is pulled manually from the EasyTide system

    TODO use https://github.com/ianByrne/PyPI-ukhotides

    """

    def __init__(self, location_id):

        self.url = "https://easytide.admiralty.co.uk/Home/GetPredictionData"

        self.params = {
            "stationId": location_id,
        }

    def fetch(self, debug=False):
        gmt = pytz.timezone("GMT")
        our_tz = get_localzone()
        sess = requests.Session()

        rsp = sess.get(self.url, params=self.params)

        if rsp.status_code == requests.codes.ok:
            if debug:
                with NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(rsp.content)
                    print("Content written to " + tmp.name)

            raw_tides = rsp.json()["tidalEventList"]
            ret = []
            now = datetime.datetime.now().replace(tzinfo=our_tz)
            for t in raw_tides:
                tide_type = "HIGH" if t["eventType"] == 0 else "LOW"
                when = datetime.datetime.fromisoformat(t["dateTime"]).replace(
                    tzinfo=gmt
                )
                if when > now:
                    ret.append(Tide(when, tide_type, t["height"]))

            logging.info("Fetched %d tides", len(ret))
            return ret

        else:
            rsp.raise_for_status()
