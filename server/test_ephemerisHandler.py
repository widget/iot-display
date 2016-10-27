from unittest import TestCase

from datetime import date, datetime, timedelta

from ephem_tools import EphemerisHandler


class TestEphemerisHandler(TestCase):
    def test_calculate_sunrise(self):
        e = EphemerisHandler((51.85,1.28))
        # summer
        e.observer.date = date(2016, 10, 27)
        self.assertAlmostEqual(e.calculate_sunrise(), datetime(2016, 10, 27, 6, 40, 0), delta=timedelta(seconds=60))

    def test_calculate_sunset(self):
        e = EphemerisHandler((51.85,1.28))
        e.observer.date = date(2016, 10, 27)
        self.assertAlmostEqual(e.calculate_sunset(), datetime(2016, 10, 27, 16, 35, 0), delta=timedelta(seconds=60))
