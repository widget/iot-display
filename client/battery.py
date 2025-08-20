"""
File for Battery class
"""

from machine import ADC


class Battery(object):
    """
    Expansion board has battery on GP3
    The ADC measures between 0-1.4V
    It is 12bit (0-4095)
    It is measuring off a 56k/(56k+115k) voltage divider - 0.32
    """

    MINIMUM = 3180  # 3.64V measured
    CHARGED = 3600  # Using 4.15V
    RANGE = CHARGED - MINIMUM

    def __init__(self):
        self.adc = ADC()
        self.battery_raw = self.adc.channel(pin="GP3")

    def __del__(self):
        self.battery_raw.deinit()
        self.adc.deinit()

    def safe(self):
        """
        Is battery at operating voltage?
        :return: True/False
        """
        return self.battery_raw() >= Battery.MINIMUM

    def value(self):
        """
        Battery percentage
        :return: 0-100
        """
        val = (self.battery_raw() - Battery.MINIMUM) * 100
        val = val // Battery.RANGE
        if val > 100:
            val = 100
        if val < 0:
            val = 0
        return val
