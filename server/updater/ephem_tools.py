from math import radians as rad
from datetime import date
import ephem
import pytz


class EphemerisHandler(object):
    def __init__(self, latlong_dd):
        self.observer = ephem.Observer()
        self.observer.name = 'Somewhere'
        self.observer.lat = rad(latlong_dd[0])  # lat/long in decimal degrees
        self.observer.long = rad(latlong_dd[1])
        self.observer.elevation = 0

        self.observer.date = date.today()

        self.observer.pressure = 1000
        self.gmt = pytz.timezone("GMT")
        #self.observer.horizon = 0

    def calculate_moon_phase(self):

        m = ephem.Moon()
        m.compute(self.observer)

        nnm = ephem.next_new_moon(self.observer.date)
        pnm = ephem.previous_new_moon(self.observer.date)
        # for use w. moon_phases.ttf A -> just past  newmoon,
        # Z just before newmoon
        # '0' is full, '1' is new
        # note that we cannot use m.phase as this is the percentage of the moon
        # that is illuminated which is not the same as the phase!
        lunation = (self.observer.date - pnm) / (nnm - pnm)
        symbol = lunation * 26
        # print("Lunation as a 1/26 is: %f" % symbol)
        if symbol < 0.5 or symbol > 25.5:
            symbol = '*'  # new moon
        else:
            symbol = chr(ord('A') + int(symbol + 0.5) - 1)
        return symbol

        # print(ephem.localtime(g.date).time(), deg(m.alt),deg(m.az),
        #  ephem.localtime(g.date).time().strftime("%H%M"),
        #  m.phase,symbol)

    def calculate_sunrise(self):
        """

        :return: ALWAYS IN GMT
        """
        s = ephem.Sun()
        return self.gmt.localize(self.observer.next_rising(s, use_center=False).datetime())

    def calculate_sunset(self):
        """

        :return: ALWAYS IN GMT
        """
        s = ephem.Sun()
        return self.gmt.localize(self.observer.next_setting(s, use_center=False).datetime())
