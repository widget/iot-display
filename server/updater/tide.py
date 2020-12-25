from lxml import etree


class Tide(object):
    def __init__(self, tide_time, tide_type, height):
        self.time = tide_time  # In GMT
        self.type = tide_type
        self.height = height

    def to_xml(self):
        top = etree.Element("tide")
        # Discarding TZ info on save as strptime imports tz in a different format
        top.attrib["time"] = self.time.strftime("%Y-%m-%dT%H:%M:%S")
        top.attrib["type"] = self.type
        top.attrib["height"] = "%.1f" % self.height

        return top

    def __str__(self):
        return "%s tide (%.2fm) at %s" % (self.type, self.height, self.time)
