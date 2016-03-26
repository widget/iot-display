
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
    A charged LiPo is 4.2V
    Minimum voltage is 3.2V
    """
    MINIMUM = 2990 # 3.2 * 0.32 / 1.4 * 4096 (ltr, cba with brackets)
    CHARGED = 3560 # Using 3.8V atm
    PERCENT = 6 # 900 Range

    def __init__(self):
        self.adc = ADC()
        self.battery_raw = self.adc.channel(pin='GP3')

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
        val = (self.battery_raw() - Battery.MINIMUM) // Battery.PERCENT
        if val > 100:
            val = 100
        return val
