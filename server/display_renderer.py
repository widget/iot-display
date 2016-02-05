
from PIL import Image, ImageDraw, ImageFont
import PIL.ImageOps
from bitstring import BitStream
from itertools import zip_longest
import struct


class DisplayRenderer(object):
    RES = (400, 300)

    def __init__(self):
        self.surface = Image.new("L", DisplayRenderer.RES, 255)
        # TODO Change this for a PIL-format font when we find one we like - it'll need to be
        # a bitmap anyway as vectors are expectingto be aliased
        self.large_font = ImageFont.truetype('Ubuntu-R.ttf', 30)
        self.small_font = ImageFont.truetype('Ubuntu-R.ttf', 16)
        self.surface_bw = None

    def clear(self):
        pass

    def _gen_bw(self):
        self.surface_bw = self.surface.convert('1')

    def render(self):
        draw = ImageDraw.Draw(self.surface)
        draw.line((0, DisplayRenderer.RES[1], DisplayRenderer.RES[0], 0), fill=0)
        draw.line((0, 0) + DisplayRenderer.RES, fill=0)
        draw.text((60,40), "This is a test", font=self.small_font, fill=0)
        draw.rectangle(((100,100),(200,200)),fill=128,outline=0)

    def save(self, path):
        self._gen_bw()
        with open(path, "wb") as output:
            self.surface_bw.save(output, "PNG")

    def export(self):
        # This one is 0.6s so much faster, but apparently uses an extra 8MB probably from pulling
        # the generator just getting pulled straight to a list

        # Get data
        self._gen_bw()
        # Invert it on the way for the display
        img_gen = (x^0xff for x in (self.surface_bw.getdata()))
        # Get header
        header = struct.pack(">B2H2B", 0x33, DisplayRenderer.RES[0], DisplayRenderer.RES[1], 1, 0) + (b"\x00"*9)
        # Splat out
        return header + BitStream(img_gen).bytes

if __name__ == "__main__":
    d = DisplayRenderer()
    d.render()
    data = d.export()
    open('data.bin', 'wb').write(data)
    d.save("data.png")
