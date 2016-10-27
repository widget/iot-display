from unittest import TestCase

from datetime import date, datetime, timedelta
import pytz
from ephem_tools import EphemerisHandler


class TestEphemerisHandler(TestCase):
    def test_calculate_sunrise(self):
        e = EphemerisHandler((51.85,1.28))
        # summer
        e.observer.date = date(2016, 10, 27)
        gmt = pytz.timezone("GMT")
        self.assertAlmostEqual(e.calculate_sunrise(),
                               gmt.localize(datetime(2016, 10, 27, 6, 40, 0)),
                               delta=timedelta(seconds=60))

    def test_calculate_sunset(self):
        e = EphemerisHandler((51.85,1.28))
        e.observer.date = date(2016, 10, 27)
        gmt = pytz.timezone("GMT")
        self.assertAlmostEqual(e.calculate_sunset(),
                               gmt.localize(datetime(2016, 10, 27, 16, 35, 0)),
                               delta=timedelta(seconds=60))
