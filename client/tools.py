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
    os.mount(sd, "/sd")

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


def print_log(path="/sd/display.log"):
    sd = SD()
    os.mount(sd, "/sd")

    with open(path, "r") as logfile:
        for line in logfile:
            print(line, end="")

    os.unmount("/sd")
    sd.deinit()


def connect_wifi(cfg=None):
    if not cfg:
        from config import Config

        cfg = Config.load(debug=True)

    from network import WLAN
    import machine

    print("Starting WLAN, attempting to connect to " + cfg.wifi_ssid)
    wlan = WLAN(0, WLAN.STA)
    wlan.ifconfig(config="dhcp")
    wlan.connect(ssid=cfg.wifi_ssid, auth=(WLAN.WPA2, cfg.wifi_key))
    while not wlan.isconnected():
        machine.idle()
    print("Connected")


def lo_power():
    from machine import Pin, deepsleep

    for pin in dir(Pin.board):
        p = Pin(pin)
        p.init(Pin.IN, pull=Pin.PULL_DOWN, alt=-1)
    deepsleep()
