
from machine import SD
import os


class Config(object):
    """
    Simple tuple for holding configuration data - also a namespace
    for mounting the SD and loading the data off it
    """
    def __init__(self, host, image, meta, upload, ap, key, port=80):
        self.host = host
        self.port = port
        self.image_path = image
        self.metadata_path = meta
        self.upload_path = upload
        self.wifi_ssid = ap
        self.wifi_key = key

    @staticmethod
    def load(debug=False, sd=None):
        # Load off SD our AP, pw, and URL details
        unmount = False
        if sd is None:
            sd = SD()
            os.mount(sd, '/sd')
            unmount = True
        host = ""
        wifi_ap = ""
        wifi_key= ""
        port = 80
        image = ""
        meta = ""
        upload = ""
        with open("/sd/config.txt", "r") as cfgfile:
            for line in cfgfile:
                line = line.strip()
                if debug:
                    print("Processing line '%s'" % line)
                try:
                    if line.startswith("Host:"):
                        host = line[5:].strip()
                    elif line.startswith("WiFi:"):
                        wifi_ap = line[5:].strip()
                    elif line.startswith("Pass:"):
                        wifi_key = line[5:].strip()
                    elif line.startswith("Port:"):
                        port = int(line[5:])
                    elif line.startswith("Image:"):
                        image = line[6:].strip()
                    elif line.startswith("Meta:"):
                        meta = line[5:].strip()
                    elif line.startswith("Up:"):
                        upload = line[3:].strip()
                except ValueError:
                    if debug:
                        print("Can't process line")

        if unmount:
            os.unmount('/sd')
            sd.deinit()
            del sd

        if host and wifi_ap and wifi_key and image and meta:
            return Config(host, image, meta, upload, wifi_ap, wifi_key, port)
        else:
            raise ValueError("No config")
