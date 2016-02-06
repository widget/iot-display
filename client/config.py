
from machine import SD
import os


class Config(object):
    """
    Simple tuple for holding configuration data - also a namespace
    for mounting the SD and loading the data off it
    """
    def __init__(self, url, ap, key, port=80):
        self.url = url
        self.port = port
        self.wifi_ssid = ap
        self.wifi_key = key

    @staticmethod
    def load(debug=False):
        # Load off SD our AP, pw, and URL details
        sd = SD()
        os.mount(sd, '/sd')
        url = ""
        wifi_ap = ""
        wifi_key= ""
        port = 80
        with open("/sd/config.txt", "r") as cfgfile:
            for line in cfgfile:
                if debug:
                    print("Processing line '%s'" % line)
                try:
                    if line.startswith("URL:"):
                        url = line[4:].strip()
                    elif line.startswith("WiFi:"):
                        wifi_ap = line[5:].strip()
                    elif line.startswith("Pass:"):
                        wifi_key = line[5:].strip()
                    elif line.startswith("Port:"):
                        port = int(line[5:].strip())
                except ValueError:
                    if debug:
                        print("Can't process line")
        os.unmount(sd)
        sd.deinit()
        del sd

        if url and wifi_ap and wifi_key:
            return Config(url,wifi_ap, wifi_key, port)
        else:
            raise ValueError("No config")
