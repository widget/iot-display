import socket
import re
import network
import machine
from config import Config
from epd import EPD
from machine import RTC, Pin

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



def init_rtc(time_tuple):
    rtc = RTC(datetime=time_tuple)
    # This interrupt doesn't have a handler as deep sleep doesn't preserve state
    rtc_i = rtc.irq(trigger=RTC.ALARM0, wake=machine.DEEPSLEEP)
    return rtc


cfg = Config.load()

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