import datetime
from unittest import TestCase

import pytz

from display_renderer import DisplayRenderer
from tide import Tide


class TestDisplayRenderer(TestCase):
    def test_render(self):
        gmt = pytz.timezone("GMT")
        now = datetime.datetime.now()
        now = gmt.localize(now)
        tide1 = Tide(now, "low", 0.8)
        default = DisplayRenderer(tide1)
        default.render()
        with_tz = DisplayRenderer(tide1, tz=gmt)
        with_tz.render()
