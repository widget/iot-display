import math
from PIL import Image, ImageDraw, ImageFont
import PIL.ImageOps

from epd_generator import EPDGenerator

from datetime import date, datetime, timedelta

from ephem_tools import EphemerisHandler


class DisplayRenderer(object):
    RES = (400, 300)

    def __init__(self, tide1, tide2=None):
        # Work in greyscale, and we can dither to monochrome
        self.surface = Image.new("L", DisplayRenderer.RES, 255)
        # TODO Find bitmap fonts
        self.large_font = ImageFont.truetype('Ubuntu-R.ttf', 30)
        self.small_font = ImageFont.truetype('Ubuntu-R.ttf', 14)
        self.moon_font  = ImageFont.truetype('./moon_phases.ttf', 42)

        self.ephem = EphemerisHandler((51.85, 1.28))

        self.surface_bw = None
        self.draw = ImageDraw.Draw(self.surface)

        self.tide1_time = "%02d:%02d" % (tide1[0].hour, tide1[0].minute)
        self.tide1_type = tide1[1].upper()
        self.tide1_height = tide1[2]

        self.battery_charge = 100
        if tide2:
            self.tide2_time = "%02d:%02d" % (tide2[0].hour, tide2[0].minute)
            self.tide2_type = tide2[1].upper()
            self.tide2_height = tide2[2]
        else:
            self.tide2_time = None

    def _gen_bw(self):
        self.surface_bw = self.surface.convert('1')

    def render(self):

        self.draw_centre_text((120, 15), "%s tide" % self.tide1_type, self.large_font)

        self.draw.line((255, 50, 255,250), fill=0)

        self.draw_clock((20, 50), (240, 265), self.tide1_time)

        self.draw_centre_text((120, 290), "Height: %.2fm" % self.tide1_height, self.small_font)

        if self.tide2_time:
            msg = "%s tide -\n\nTime: %s\nHeight: %.2fm" % (self.tide2_type, self.tide2_time, self.tide2_height)
        else:
            msg = "Next tide\n tomorrow"
        self.draw.multiline_text((270,10), msg, font=self.small_font, align="left", spacing=5)

        msg = "Sunrise: %s\nSunset: %s" % (self.ephem.calculate_sunrise().strftime("%H:%M"),
                                           self.ephem.calculate_sunset().strftime("%H:%M"))

        self.draw.multiline_text((270, 180), msg, font=self.small_font, align="left", spacing=5)

        self.draw.text((270, 230), self.ephem.calculate_moon_phase(), font=self.moon_font)

        # Battery icon and percentage

        pos = (340, 235)
        self.draw.rectangle(((pos[0], pos[1]+5), (pos[0]+5, pos[1]+10)), outline=0)
        self.draw.rectangle(((pos[0]+5, pos[1]), (pos[0]+35, pos[1]+15)), outline=0)
        self.draw.text((pos[0], pos[1]+20), "%02d%%" % self.battery_charge, font=self.small_font)

        # Date this ran on
        msg = "%s" % datetime.now().strftime("%a, %d %b %Y")
        self.draw.text((270, 280), msg, font=self.small_font)

        pos = (265, 100)
        self.draw_wind(pos, (pos[0]+60, pos[1]+60), "13", 270)

    def draw_wind(self, tl, br, speed, angle):
        size = (br[0] - tl[0], br[1] - tl[1])
        centre = (tl[0] + size[0]/2, tl[1] + size[1]/2)

        r = float(angle) / 360.0

        self.draw.ellipse(((centre[0]-(size[0]*0.2), centre[1]-(size[1]*0.2)),
                           (centre[0]+(size[0]*0.2), centre[1]+(size[1]*0.2))),
                          outline=0)

        self.draw.line((DisplayRenderer.polar_to_cartesian(tl, br, 0.4, r),
                        DisplayRenderer.polar_to_cartesian(tl, br, 0.9, r)),
                       fill=0, width=5)
        arrow_head = [
            (DisplayRenderer.polar_to_cartesian(tl, br, 0.8, r-0.04)),
            (DisplayRenderer.polar_to_cartesian(tl, br, 1, r)),
            (DisplayRenderer.polar_to_cartesian(tl, br, 0.8, r+0.04))
        ]
        self.draw.polygon(arrow_head, outline=0, fill=0)
        self.draw_centre_text(centre, speed, font=self.small_font)

    def draw_centre_text(self, xy, msg, font, fill=0):
        width = self.draw.textsize(msg, font=font)
        self.draw.text((xy[0]-(width[0]/2), xy[1]-(width[1]/2)), msg, font=font, fill=fill)

    @staticmethod
    def polar_to_cartesian(tl, br, mag, angle):
        size = (br[0] - tl[0], br[1] - tl[1])
        centre = (tl[0] + size[0]/2, tl[1] + size[1]/2)
        rad = 2 * angle * math.pi

        x = centre[0] + int(0.5 * mag * size[0] * math.sin(rad))
        y = centre[1] - int(0.5 * mag * size[1] * math.cos(rad))

        return x, y

    def draw_clock(self, tl, br, time):

        size = (br[0] - tl[0], br[1] - tl[1])
        centre = (tl[0] + size[0]/2, tl[1] + size[1]/2)
        hour, minute = time.split(':')
        hour = int(hour)
        minute = int(minute)
        if hour > 12:
            hour -= 12
        minute = float(minute)/60
        hour = (float(hour) + minute)/12

        # self.draw.ellipse((tl, br), fill=None, outline=0)

        # Face
        for i in range(12):
            r = float(i)/12
            self.draw.line((DisplayRenderer.polar_to_cartesian(tl, br, 0.95, r),
                            DisplayRenderer.polar_to_cartesian(tl, br, 1, r)), fill=0)

        little_hand_dim = (0.05, 0.55)
        big_hand_dim = (0.075, 0.9)

        # Little hand
        little_hand = [
            DisplayRenderer.polar_to_cartesian(tl, br, little_hand_dim[0], hour+0.5),
            DisplayRenderer.polar_to_cartesian(tl, br, little_hand_dim[0], hour+0.25),
            DisplayRenderer.polar_to_cartesian(tl, br, little_hand_dim[1], hour),
            DisplayRenderer.polar_to_cartesian(tl, br, little_hand_dim[0], hour-0.25)]

        # Big hand
        big_hand = [
            DisplayRenderer.polar_to_cartesian(tl, br, big_hand_dim[0], minute+0.5),
            DisplayRenderer.polar_to_cartesian(tl, br, big_hand_dim[0], minute+0.25),
            DisplayRenderer.polar_to_cartesian(tl, br, big_hand_dim[1], minute),
            DisplayRenderer.polar_to_cartesian(tl, br, big_hand_dim[0], minute-0.25)]

        self.draw.polygon(big_hand, outline=0, fill=200)
        self.draw.polygon(little_hand, outline=0, fill=100)

    def save(self, path):
        self._gen_bw()
        with open(path, "wb") as output:
            self.surface_bw.save(output, "PNG")


if __name__ == "__main__":
    d = DisplayRenderer((datetime.now(), "high", 3.33), (datetime.now()+timedelta(hours=6), "low", -0.33))
    d.render()
    d.save("data.png")

    e = EPDGenerator(d.surface_bw)
    e.save("data.bin")
    print("Checksum is 0x%x" % e.checksum())
