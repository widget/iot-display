from unittest import TestCase

import sys
from unittest.mock import MagicMock, Mock

sys.modules["machine"] = MagicMock()

from battery import Battery


class TestBattery(TestCase):
    def test_safe(self):
        b = Battery()
        b.battery_raw = MagicMock(side_effect=[3400, 3800])
        self.assertEqual(b.safe(), False)
        self.assertEqual(b.safe(), True)

    def test_value(self):
        b = Battery()
        b.battery_raw = MagicMock(side_effect=[3500, 3800, 5000])
        self.assertEqual(b.value(), 0)
        self.assertEqual(b.value(), 100)
