
from machine import SD
import os

"""
Helper functions we won't be loading in normal operation to save RAM
"""


def save_config(cfg):
    """
    Save out a configuration file
    :param Config cfg: config option
    :return: None
    """
    sd = SD()
    os.mount(sd, '/sd')

    with open("/sd/config.txt", "w") as cfgfile:
        cfgfile.write("Host:%s\n", cfg.host)
        cfgfile.write("WiFi:%s\n", cfg.wifi_ssid)
        cfgfile.write("Pass:%s\n", cfg.wifi_key)
        cfgfile.write("Port:%s\n", cfg.port)
        cfgfile.write("Image:%s\n", cfg.image_path)
        cfgfile.write("Meta:%s\n", cfg.metadata_path)
        if cfg.upload_path:
            cfgfile.write("Up:%s\n", cfg.upload_path)
    os.unmount(sd)
    sd.deinit()


def load_file(path):
    with open(path, "rb") as f:
        return f.read()


def print_log(path='/sd/display.log'):
    sd = SD()
    os.mount(sd, '/sd')

    with open(path, 'r') as logfile:
        for line in logfile:
            print(line)

    os.unmount(sd)
    sd.deinit()