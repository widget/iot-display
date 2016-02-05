import socket
import re
import network
import machine
import os

from epd import EPD
from machine import SPI, RTC, Pin, SD

# Pins in use:
# GPIO1 - TxD
# GPIO2 - RxD
# GPIO3 - Vbatt
# GPIO4 - EPD busy
# GPIO5 - EPD enable


# GPIO10 SD0CLK
# GPIO11 SD0CMD

# GPIO15 SD0DATA
# GPIO16 EPD MOSI
# GPIO17 EPD CS

# GP25 - heartbeat

# GPIO30 - EPD MISO
# GPIO31 - EPD CLK

class Config(object):
    def __init__(self, url, ap, key):
        self.url = url
        self.wifi_ssid = ap
        self.wifi_key = key


def init_rtc(time_tuple):
    rtc = RTC(datetime=time_tuple)
    # This interrupt doesn't have a handler as deep sleep doesn't preserve state
    rtc_i = rtc.irq(trigger=RTC.ALARM0, wake=machine.DEEPSLEEP)
    return rtc


def load_config():
    # Load off SD our AP, pw, and URL details
    sd = SD()
    os.mount(sd, '/sd')
    url = ""
    wifi_ap = ""
    wifi_key= ""
    with open("/sd/config.txt", "r") as cfgfile:
        for line in cfgfile:
            if line.startswith("URL:"):
                url = line[4:].strip()
            elif line.startswith("WiFi:"):
                wifi_ap = line[5:].strip()
            elif line.startswith("Pass:"):
                wifi_key = line[5:].strip()
    os.unmount(sd)
    sd.deinit()

    if url and wifi_ap and wifi_key:
        return Config(url,wifi_ap, wifi_key)
    else:
        raise ValueError("No config")


def simple_strptime(date_str):
    """
    Decode a date of a fixed form
    :param date_str: Of the form  "Sun, 31 Jan 2016 14:16:24 GMT"
    :return: tuple (2016,1,31,14,16,24)
    """
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    date = re.compile(r'(\d+) (\w+) (\d+) (\d+):(\d+):(\d+)', )
    res = date.search(date_str)
    month = MONTHS.index(res.group(2))
    return res.group(3), month, res.group(1), res.group(4), res.group(5), res.group(6)


def fetch_image(url):
    bits = url.split('/')
    host = bits[0]
    path = "/".join(bits[1:])
    del bits

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    loc = socket.getaddrinfo(url.split('/')[0], 80)[0][4]

    req = 'GET {path} HTTP/1.0\nHost: {host}\n'.format(host=host, path=path)
    # TODO try deflate here?  Would help an awful lot but uzlib isn't present
    req += 'User-Agent: TideClock/1.0\nAccept-Encoding: identity\n\n'

    req = req.encode()
    sock.connect(loc)
    sock.send(req)
    response = sock.recv(18000)  # The file should always be 15016 bytes if uncompressed
    sock.close()
    del sock

    headers, content = response.split(b'\r\n\r\n')
    del response
    headers = headers.decode()
    headers = headers.splitlines()

    if "OK" not in headers[0]:
        # Gracefully fail
        return

    length = 0
    content_type = ""
    time_tuple = (0, 0, 0, 0, 0, 0)
    for line in headers[1:]:
        arg = line.split(':')[-1].strip()
        if "Date" in line:
            # Grab time and keep it
            time_tuple = simple_strptime(line)
        elif "Content-Length" in line:
            #  Extract the length
            length = int(arg)
        elif "Content-Type" in line:
            content_type = arg

    if length != 0 and length == len(content) and "octet-stream" in content_type:
        return time_tuple, content
    else:
        # TODO raise things
        pass


cfg = load_config()

wlan = network.WLAN(mode=network.WLAN.STA)
nets = wlan.scan()
for net in nets:
    if net.ssid == cfg.wifi_ssid:
        print('Network found!')
        wlan.connect(net.ssid, auth=(net.sec, cfg.wifi_key), timeout=5000)
        while not wlan.isconnected():
            machine.idle() # save power while waiting
        print('WLAN connection succeeded!')
        break

servertime, content = fetch_image(cfg.url)
init_rtc(servertime)

wipy.heartbeat(False)
machine.deepsleep()