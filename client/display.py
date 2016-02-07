import gc
import machine

from battery import Battery
from config import Config
from connect import Connect
from epd import EPD
from machine import RTC, Pin, WDT
import wipy

# Pins in use:
# GPIO1 - TxD
# GPIO2 - RxD
# GPIO3 - Vbatt
# GPIO4 - EPD enable
# GPIO5 - EPD busy

# GPIO10 SD0CLK
# GPIO11 SD0CMD

# GPIO15 SD0DATA
# GPIO16 EPD MOSI
# GPIO17 EPD CS

# GP25 - heartbeat

# GPIO30 - EPD MISO
# GPIO31 - EPD CLK


class Display(object):
    IMG_DIR = '/flash/imgs'
    def __init__(self, debug=False):
        self.cfg = None
        self.rtc = RTC()
        self.debug = debug

        if not debug:
            self.wdt = WDT(timeout=20000)
            self.sd = None
        else:
            from machine import SD
            from os import mount, unmount
            self.sd = SD()
            mount(self.sd, '/sd')
            self.logfile = open("/sd/display.log", "a")

        self.epd = EPD()

        # Don't flash when we're awake outside of debug
        wipy.heartbeat(self.debug)

    def log(self, msg, end='\n'):
        if self.debug:
            time = "%d, %d, %d, %d, %d, %d" % self.rtc.now()[:-2]
            msg = time + ", " + msg
            self.logfile.write(msg + end)
            print(msg, end=end)

    def feed_wdt(self):
        if not self.debug:
            self.wdt.feed()

    def connect_wifi(self):
        from network import WLAN

        self.log('Starting WLAN, attempting to connect to ' + self.cfg.wifi_ssid)
        wlan = WLAN(0, WLAN.STA)
        wlan.ifconfig(config='dhcp')
        wlan.connect(ssid=self.cfg.wifi_ssid, auth=(WLAN.WPA2, self.cfg.wifi_key))
        while not wlan.isconnected():
            machine.idle()
        self.log('Connected')

        # TODO check this
        # del WLAN

    @staticmethod
    def reset_cause():
        val = machine.reset_cause()
        if val == machine.POWER_ON:
            return "power"
        elif val == machine.HARD_RESET:
            return "hard"
        elif val == machine.WDT_RESET:
            return "wdt"
        elif val == machine.DEEPSLEEP_RESET:
            return "sleep"
        elif val == machine.SOFT_RESET:
            return "soft"

    def set_alarm(self, now, json_metadata):
        import json
        json_dict = json.loads(json_metadata)

        # Now we know the time too
        self.rtc = RTC(datetime=now)
        list_int = json_dict["wakeup"][:6]
        time_str = ",".join([str(x) for x in list_int])

        self.log("Setting alarm for " + time_str)
        self.rtc.alarm(time=tuple(list_int))

        del json

    def display_file_image(self, path):

        with open(path, 'rb') as f:

            while True:
                buff = f.read(250)
                self.epd.upload_image_data(buff, delay_us=1000)
                self.feed_wdt()

                # EOF
                if len(buff) < 250:
                    break

        self.epd.display_update()

    def display_no_config(self):
        self.log("Displaying no config msg")
        self.display_file_image(Display.IMG_DIR + '/no_config.bin')

    def display_low_battery(self):
        self.log("Displaying low battery msg")
        self.display_file_image(Display.IMG_DIR + '/low_battery.bin')

    def display_cannot_connect(self):
        self.log("Displaying no server comms msg")
        self.display_file_image(Display.IMG_DIR + '/no_server.bin')

    def display_no_wifi(self):
        self.log("Displaying no wifi msg")
        self.display_file_image(Display.IMG_DIR + '/no_wifi.bin')

    def run_deepsleep(self):
        self.run()

        # Close files on the SD card
        if self.sd:
            self.logfile.close()
            unmount('/sd')
            self.sd.deinit()

        # Set the wakeup (why do it earlier?)
        rtc_i = self.rtc.irq(trigger=RTC.ALARM0, wake=machine.DEEPSLEEP)

        self.log("Going to sleep, waking in %dms" % self.rtc.alarm_left())

        # Turn the screen off
        self.epd.disable()

        # Basically turn off
        machine.deepsleep()

    def run(self):

        battery = Battery()

        self.epd.enable()

        if not battery.safe():
            self.log("Battery voltage low! Turning off")
            self.feed_wdt()
            self.display_low_battery()
            return
        else:
            self.log("Battery value: %d" % battery.value())

        try:
            self.cfg = Config.load(sd=self.sd)
            self.log("Loaded config")
        except (OSError, ValueError) as e:
            self.log("Failed to load config: " + str(e))
            self.display_no_config()
            return

        self.feed_wdt()

        # TODO connect to wifi
        self.connect_wifi()

        try:
            self.log("Connecting to server %s:%d" % (self.cfg.host, self.cfg.port))
            c = Connect(self.cfg.host, self.cfg.port, debug=self.debug)

            self.feed_wdt()

            self.log("Reset cause: " + Display.reset_cause())

            if len(self.cfg.upload_path) > 0:
                temp = self.epd.get_sensor_data()
                c.post(self.cfg.upload_path,
                       battery=battery.value(),
                       reset=Display.reset_cause(),
                       screen=temp)

            self.log("Fetching metadata from " + self.cfg.metadata_path)
            metadata = c.get(self.cfg.metadata_path, max_length=1024, path_type='json')
            self.set_alarm(c.last_fetch_time, metadata)

            self.feed_wdt()
            del metadata
            del battery
            self.log("Fetching image from " + self.cfg.image_path)
            gc.collect()

            content = c.get(self.cfg.image_path)

            self.feed_wdt()
            self.log("Uploading to display")

            self.epd.upload_whole_image(content)

            self.feed_wdt()
            self.log("Refreshing display.")
            self.epd.display_update()

            self.log("Finished. Mem free: %d" % gc.mem_free())
        except (RuntimeError, ValueError) as e:
            self.log("Failed to update display: " + str(e))
            self.display_cannot_connect()
            self.rtc.alarm(time=3600000)
