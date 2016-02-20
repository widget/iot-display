import datetime

import re
from tempfile import NamedTemporaryFile

from bs4 import BeautifulSoup
import requests


class TideParser(object):
    """
    Parses the tidetimes RSS feed for something less crap.  BeautifulSoup4 is depending on
    LXML as RSS is XML, but the HTML in the RSS needs extracting.

    No errors are handled yet, Requests could return ConnectionError or Timeout

    The format of an entry is:

    <description>&lt;a href=&quot;https://www.tidetimes.org.uk&quot; title=&quot;tide times&quot;&gt;Tide Times&lt;/a&gt; &amp; Heights for &lt;a href=&quot;https://www.tidetimes.org.uk/walton-on-the-naze-tide-times&quot; title=&quot;Walton-on-the-Naze tide times&quot;&gt;Walton-on-the-Naze&lt;/a&gt; on 30th January 2016&lt;br/&gt;&lt;br/&gt;03:10 - High Tide &#x28;3.96m&#x29;&lt;br/&gt;09:16 - Low Tide &#x28;0.56m&#x29;&lt;br/&gt;15:33 - High Tide &#x28;3.76m&#x29;&lt;br/&gt;21:18 - Low Tide &#x28;0.96m&#x29;&lt;br/&gt;</description>
    """

    URL="http://www.tidetimes.org.uk/walton-on-the-naze-tide-times.rss"

    def __init__(self):
        self.tidematch = re.compile(r"""(?P<time>[0-2][0-9]:[0-5][0-9])
                                        \W+-\W+
                                        (?P<type>High|Low)\ Tide\W+
                                        \((?P<height>-*\d+.\d+)m\)""",
                                    re.VERBOSE)
        self.xml_time_fmt = "%a, %d %b %Y %H:%M:%S %Z"

    def fetch(self, debug=False):
        sess = requests.Session()
        rsp = sess.get(TideParser.URL)

        if rsp.status_code == requests.codes.ok:
            if debug:
                with NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(rsp.content)
                    print("Content written to " + tmp.name)

            feed_doc = BeautifulSoup(rsp.content, "xml")

            updated_str = feed_doc.channel.lastBuildDate.text
            updated = datetime.datetime.strptime(updated_str, self.xml_time_fmt)

            latest = feed_doc.channel.item.description.text
            latest_time = datetime.datetime.strptime(feed_doc.channel.item.pubDate.text, self.xml_time_fmt)

            ret = []

            # Split on br tags and drop the title and empty line
            for tide_time in self.tidematch.finditer(latest):
                vals = tide_time.groupdict()
                time = datetime.time(*[int(x) for x in vals["time"].split(':')])
                ttype = vals["type"]
                height = float(vals["height"])

                ret.append((datetime.datetime.combine(latest_time.date(), time), ttype, height))

            return ret

        else:
            rsp.raise_for_status()
