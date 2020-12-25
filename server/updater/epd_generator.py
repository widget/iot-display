"""
Class for managing EPD files and also generates them on the cmdline
"""

import glob
import os

from bitstring import BitStream
from PIL import Image
import struct


class EPDGenerator(object):
    """
    Takes PIL images and converts them to monochrome, then can save them out
    """

    def __init__(self, surface):
        if surface.mode == "1":
            self.surface = surface
        else:
            self.surface = surface.convert("1")

    @staticmethod
    def from_file(path):
        """
        Helper function
        :param path: Loads any PIL-supported file
        :return:
        """
        im = Image.open(path)
        return EPDGenerator(im)

    @staticmethod
    def process_files(src_dir, dest_dir):
        """
        Helper function, defaults to PNGs
        :param src_dir:
        :param dest_dir:
        :return:
        """
        for input_file in glob.glob(src_dir + os.sep + "*.png"):
            try:
                e = EPDGenerator.from_file(input_file)
                name = input_file.split(os.sep)[-1]
                name = name[:-4] + ".bin"
                e.save(dest_dir + os.sep + name)
                print("Checksum: 0x%x" % e.checksum())
                print("Saved " + name)
            except OSError:
                print("Couldn't convert " + input_file)

    def checksum(self):
        """
        Not sure if this is right, doesn't match the display's generated values
        :return:
        """
        acc = 0x6363
        img_gen = (x for x in (self.surface.getdata()))
        data = BitStream(img_gen).bytes

        for byte in data:
            acc ^= byte
            acc = ((acc >> 8) | (acc << 8)) & 0xFFFF
            acc ^= ((acc & 0xFF00) << 4) & 0xFFFF
            acc ^= (acc >> 8) >> 4
            acc ^= (acc & 0xFF00) >> 5
        return acc

    def save(self, path):
        """
        EPD format 0 so you know
        :param path:
        :return:
        """
        with open(path, "wb") as output:
            # Invert it on the way for the display
            img_gen = (x ^ 0xFF for x in (self.surface.getdata()))
            # Get header
            header = struct.pack(
                ">B2H2B", 0x33, self.surface.size[0], self.surface.size[1], 1, 0
            ) + (b"\x00" * 9)
            # Splat out
            output.write(header + BitStream(img_gen).bytes)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert a directory of PNGs to EPDs")
    parser.add_argument("-s", "--source", help="Source directory")
    parser.add_argument("-d", "--dest", help="Destination directory")

    args = parser.parse_args()

    EPDGenerator.process_files(args.source, args.dest)
