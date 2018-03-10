
from machine import SD
import os


class Config(object):
    """
    Simple tuple for holding configuration data - also a namespace
    for mounting the SD and loading the data off it
    """
    FLASH_CONFIG_PATH = "/flash/data/config.txt"
    SD_CONFIG_PATH = "/sd/config.txt"

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
        """
         Load off SD our AP, pw, and URL details
        :param debug: Logging
        :param sd: SD object if mounted already
        :return: Config object
        """
        cfg = None
        try:
            unmount = False
            if sd is None:
                sd = SD()
                os.mount(sd, '/sd')
                unmount = True

            cfg = Config.load_file(Config.SD_CONFIG_PATH, debug)

            if unmount:
                try:
                    os.unmount('/sd') # got renamed in upy 1.9
                except AttributeError:
                    os.umount('/sd')
                sd.deinit()
                del sd
        except OSError:
            print("Can't open config file SD card")

        if not cfg:
            cfg = Config.load_file(Config.FLASH_CONFIG_PATH, debug)
            if not cfg:
                raise ValueError("No config file!")
            print("Loaded from flash")
            cfg.src = "flash"
        else:
            print("Loaded from SD card")
            cfg.src = "sd"
        return cfg

    @staticmethod
    def load_file(path, debug=False):
        host = ""
        wifi_ap = ""
        wifi_key= ""
        port = 80
        image = ""
        meta = ""
        upload = ""
        with open(path, "r") as cfgfile:
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

        if host and wifi_ap and wifi_key and image and meta:
            return Config(host, image, meta, upload, wifi_ap, wifi_key, port)
        else:
            return None

    @staticmethod
    def transfer():
        """
        Transfer an (assumed good) config file from SD to flash.

        Also assumes SD card is mounted
        :return: No return
        """
        with open(Config.SD_CONFIG_PATH, "r") as src:
            with open(Config.FLASH_CONFIG_PATH, "w") as dst:
                for line in src:
                    dst.write(line)

        os.remove(Config.SD_CONFIG_PATH)