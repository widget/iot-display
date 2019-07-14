from typing import Optional

import requests
from lxml import etree


class Weather(object):
    COMPASS = {
        "N" : 0,
        "NNE" : 22,
        "NE" : 45,
        "ENE" : 67,
        "E" : 90,
        "ESE" : 112,
        "SE" : 135,
        "SSE" : 147,
        "S" : 180,
        "SSW" : 202,
        "SW" : 225,
        "WSW" : 247,
        "W" : 270,
        "WNW" : 292,
        "NW": 315,
        "NNW" : 337,
    }

    def __init__(self, key):
        self.marine = None
        self.land = None
        self.api_key = key

    def fetch_land_observ(self, weather_id):
        # walton forecast id 354073
        # http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/xml/354073?res=3hourly&key=xxx

        # <SiteRep>
        # <Wx>
        # <Param name="F" units="C">Feels Like Temperature</Param>
        # <Param name="G" units="mph">Wind Gust</Param>
        # <Param name="H" units="%">Screen Relative Humidity</Param>
        # <Param name="T" units="C">Temperature</Param>
        # <Param name="V" units="">Visibility</Param>
        # <Param name="D" units="compass">Wind Direction</Param>
        # <Param name="S" units="mph">Wind Speed</Param>
        # <Param name="U" units="">Max UV Index</Param>
        # <Param name="W" units="">Weather Type</Param>
        # <Param name="Pp" units="%">Precipitation Probability</Param>
        # </Wx>
        # <DV dataDate="2016-02-20T12:00:00Z" type="Forecast">
        # <Location i="354073" lat="51.8477" lon="1.2695" name="WALTON ON THE NAZE" country="ENGLAND" continent="EUROPE" elevation="7.0">
        # <Period type="Day" value="2016-02-20Z">
        # <Rep D="WSW" F="5" G="27" H="85" Pp="5" S="13" T="8" V="GO" W="7" U="1">540</Rep>
        # <Rep D="SW" F="7" G="27" H="77" Pp="12" S="16" T="10" V="GO" W="7" U="1">720</Rep>
        # <Rep D="SW" F="5" G="29" H="92" Pp="97" S="18" T="9" V="MO" W="15" U="1">900</Rep>
        # <Rep D="WSW" F="7" G="36" H="91" Pp="60" S="22" T="11" V="GO" W="12" U="0">1080</Rep>
        # <Rep D="WSW" F="7" G="38" H="88" Pp="13" S="25" T="11" V="VG" W="8" U="0">1260</Rep>
        # </Period>
        # text is minutes after midnight

        sess = requests.Session()
        opts = {
            "res": "3hourly",
            "key": self.api_key
        }
        rsp = sess.get("http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/xml/%s" % weather_id, params=opts)

        if rsp.status_code != 200:
            raise RuntimeError("Bad response from Met Office for land data: %d" % rsp.status_code)

        self.land = etree.fromstring(rsp.content)
        if self.land.find('DV/Location/Period[1]/Rep[1]') is None:
            self.land = None
            raise ValueError("Warning: no final weather data found, printing response: " + rsp.text)

    def get_wind_speed(self):
        """

        :return: Wind speed (not gusts) in mph
        """
        return float(self.land.find('DV/Location/Period[1]/Rep[1]').attrib["S"])

    def get_wind_direction(self):
        """
        Wind direction
        :return: Degrees clockwise from north
        """
        return Weather.COMPASS[self.get_wind_direction_compass()]

    def get_wind_direction_compass(self):
        """
        Wind direction
        :return: 16 point compass direction as a string (e.g. WSW)
        """
        return self.land.find('DV/Location/Period[1]/Rep[1]').attrib["D"]

    def get_temperature(self):
        """

        :return: Temperature in Celsius
        """
        return float(self.land.find('DV/Location/Period[1]/Rep[1]').attrib["T"])

    def get_uv(self):
        """
        Get UV as WHO index (range is 1-8 for the UK)
        :return:
        """
        val = int(self.land.find('DV/Location/Period[1]/Rep[1]').attrib["U"])
        if val <= 2:
            val_str = "Low"
        elif val <= 5:
            val_str = "Medium"
        elif val <= 7:
            val_str = "High!"
        elif val <=10:
            val_str = "Very high!"
        else:
            val_str = "EXTREME"
        return val_str

    def fetch_sea_observ(self, weather_id):

        # Get sea temp from marine observation F3 - 162170
        # http://datapoint.metoffice.gov.uk/public/data/val/wxmarineobs/all/xml/162170?res=hourly&time=2016-02-19T12:00:00Z&key=xxx

        # Response

        # <SiteRep>
        # <Wx>
        # <Param name="T" units="C">Temperature</Param>
        # <Param name="V" units="nmi">Visibility</Param>
        # <Param name="D" units="compass">Wind Direction</Param>
        # <Param name="W" units="">Weather Type</Param>
        # <Param name="P" units="hpa">Pressure</Param>
        # <Param name="Pt" units="Pa/s">Pressure Tendency</Param>
        # <Param name="Dp" units="C">Dew Point</Param>
        # <Param name="H" units="%">Screen Relative Humidity</Param>
        # <Param name="St" units="C">Sea Temperature</Param>
        # <Param name="S" units="kn">Wind Speed</Param>
        # <Param name="Wh" units="m">Wave Height</Param>
        # <Param name="Wp" units="s">Wave Period</Param>
        # </Wx>
        # <DV dataDate="2016-02-20T12:00:00Z" type="ShipSynops">
        # <Location i="162170" lat="51.24" lon="2.0" name="F3">
        # <Period type="Day" value="2016-02-19Z">
        # <Rep D="SW" H="67.7" P="1018" S="13" T="7.2" Dp="1.7" Wh="0.2" Wp="5.0" St="8.9">720</Rep>
        # </Period>
        # </Location>
        # </DV>
        # </SiteRep>

        sess = requests.Session()
        opts = {
            "res": "hourly",
            "key": self.api_key
        }
        rsp = sess.get("http://datapoint.metoffice.gov.uk/public/data/val/wxmarineobs/all/xml/%s" % weather_id, params=opts)

        if rsp.status_code != 200:
            raise RuntimeError("Bad response from Met Office for marine data: %d" % rsp.status_code)

        self.marine = etree.fromstring(rsp.content)
        if self.marine.find('DV/Location/Period[last()]/Rep[last()]') is None:
            self.marine = None
            raise ValueError("Warning: no final weather data found, printing response: " + self.marine.text)

    @property
    def onshore(self) -> bool:
        return not self.land is None

    @property
    def offshore(self) -> bool:
        return not self.marine is None

    def get_sea_temp(self) -> Optional[float]:
        if self.marine:
            return float(self.marine.find('DV/Location/Period[last()]/Rep[last()]').attrib["St"])

    def get_wave_height(self) -> Optional[float]:
        if self.marine:
            return float(self.marine.find('DV/Location/Period[last()]/Rep[last()]').attrib["Wh"])

    def get_wave_period(self) -> Optional[float]:
        if self.marine:
            return float(self.marine.find('DV/Location/Period[last()]/Rep[last()]').attrib["Wp"])