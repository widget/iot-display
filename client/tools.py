
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
    url = ""
    wifi_ap = ""
    wifi_key= ""
    with open("/sd/config.txt", "w") as cfgfile:
        cfgfile.write("URL:%s\n", cfg.url)
        cfgfile.write("WiFi:%s\n", cfg.wifi_ssid)
        cfgfile.write("Pass:%s\n", cfg.wifi_key)
    os.unmount(sd)
    sd.deinit()
    del sd


def load_file(path):
    with open(path, "rb") as f:
        return f.read()

