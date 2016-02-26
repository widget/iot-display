
import xml.etree.ElementTree as ET


class Tide(object):
    def __init__(self, tide_time, tide_type, height):
        self.time = tide_time
        self.type = tide_type
        self.height = height

    def to_xml(self):
        top = ET.Element("tide")
        top.attrib["time"] = self.time.isoformat()
        top.attrib["type"] = self.type
        top.attrib["height"] = "%.2f" % self.height

        return top

    def __str__(self):
        return "%s tide (%.2fm) at %s" % (self.type, self.height, self.time)
