import gc

from battery import Battery
from config import Config
from connect import Connect
from epd import EPD
from machine import RTC, Pin, WDT, idle, deepsleep, DEEPSLEEP
from os import mount
try:
    from os import unmount
except ImportError:
    # This changed name in micropython 1.9
    from os import umount as unmount
from time import sleep_ms
from wipy import heartbeat

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

        # use this pin for debug
        self.wifi_pin = Pin("GP24", mode=Pin.IN, pull=Pin.PULL_UP)

        # Empty WDT object
        self.wdt = None

        if not debug:
            if not self.wifi_pin():
                self.wdt = WDT(timeout=20000)
            self.sd = None
        else:
            from machine import SD
            try:
                self.sd = SD()
                mount(self.sd, '/sd')
                self.logfile = open("/sd/display.log", "a")
            except OSError:
                self.sd = None
                self.logfile = None

        self.epd = EPD()

        self.log("Time left on the alarm: %dms" % self.rtc.alarm_left())

        # Don't flash when we're awake outside of debug
        heartbeat(self.debug)

    def log(self, msg, end='\n'):
        time = "%d, %d, %d, %d, %d, %d" % self.rtc.now()[:-2]
        msg = time + ", " + msg
        if self.logfile:
            self.logfile.write(msg + end)
        print(msg, end=end)

    def feed_wdt(self):
        if self.wdt:
            self.wdt.feed()

    def connect_wifi(self):
        from network import WLAN

        if not self.cfg:
            raise ValueError("Can't initialise wifi, no config")

        self.log('Starting WLAN, attempting to connect to ' + ','.join(self.cfg.wifis.keys()))
        wlan = WLAN(0, WLAN.STA)
        wlan.ifconfig(config='dhcp')
        while not wlan.isconnected():
            nets = wlan.scan()
            for network in nets:
                if network.ssid in self.cfg.wifi.keys():
                    self.log('Connecting to ' + network.ssid)
                    self.feed_wdt() # just in case
                    wlan.connect(ssid=network.ssid, auth=(network.sec, self.cfg.wifi[network.ssid]))
                    while not wlan.isconnected():
                        idle()
                    break

            self.feed_wdt() # just in case
            sleep_ms(2000)

        self.log('Connected as %s' % wlan.ifconfig()[0])

    @staticmethod
    def reset_cause():
        import machine
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

        if self.rtc.alarm_left() == 0:
            self.log("Alarm failed, setting for +1 hour")
            self.rtc.alarm(time=3600000)

        del json

    def display_file_image(self, file_obj):
        towrite = 15016
        max_chunk = 250
        while towrite > 0:
            c = max_chunk if towrite > max_chunk else towrite
            buff = file_obj.read(c)
            self.epd.upload_image_data(buff, delay_us=2000)
            self.feed_wdt()
            towrite -= c

        self.epd.display_update()

    def display_no_config(self):
        self.log("Displaying no config msg")
        with open(Display.IMG_DIR + '/no_config.bin', 'rb') as pic:
            self.display_file_image(pic)

    def display_low_battery(self):
        self.log("Displaying low battery msg")
        with open(Display.IMG_DIR + '/low_battery.bin', 'rb') as pic:
            self.display_file_image(pic)

    def display_cannot_connect(self):
        self.log("Displaying no server comms msg")
        with open(Display.IMG_DIR + '/no_server.bin', 'rb') as pic:
            self.display_file_image(pic)

    def display_no_wifi(self):
        self.log("Displaying no wifi msg")
        with open(Display.IMG_DIR + '/no_wifi.bin', 'rb') as pic:
            self.display_file_image(pic)

    def run_deepsleep(self):
        self.run()

        # Set the wakeup (why do it earlier?)
        rtc_i = self.rtc.irq(trigger=RTC.ALARM0, wake=DEEPSLEEP)

        self.log("Going to sleep, waking in %dms" % self.rtc.alarm_left())

        # Close files on the SD card
        if self.sd:
            self.logfile.close()
            self.logfile = None
            unmount('/sd')
            self.sd.deinit()

        # Turn the screen off
        self.epd.disable()

        if not self.wifi_pin():
            # Basically turn off
            deepsleep()
        else:
            self.log("DEBUG MODE: Staying awake")
            pass
            # Do nothing, allow network connections in

    def run(self):

        woken = self.wifi_pin()

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
            self.epd.get_sensor_data()
        except ValueError:
            self.log("Can't communicate with display, flashing light and giving up")
            heartbeat(True)
            sleep_ms(15000)
            return

        if self.rtc.alarm_left() > 0:
            self.log("Woken up but the timer is still running, refreshing screen only")
            self.epd.display_update()
            self.feed_wdt()
            return

        try:
            self.cfg = Config.load(sd=self.sd)
            self.log("Loaded config")
        except (OSError, ValueError) as e:
            self.log("Failed to load config: " + str(e))
            self.display_no_config()
            try:
                self.connect_wifi()
            except:
                pass # everything

            while True:
                sleep_ms(10)
                self.feed_wdt()

        self.feed_wdt()

        self.connect_wifi()

        content = b''
        try:
            self.log("Connecting to server %s:%d" % (self.cfg.host, self.cfg.port))
            c = Connect(self.cfg.host, self.cfg.port, debug=self.debug)

            self.feed_wdt()

            cause = Display.reset_cause()
            if woken:
                cause = "user"

            self.log("Reset cause: " + cause)

            if len(self.cfg.upload_path) > 0:
                temp = self.epd.get_sensor_data() # we read this already
                c.post(self.cfg.upload_path,
                       battery=battery.value(),
                       reset=cause,
                       screen=temp)

            self.log("Fetching metadata from " + self.cfg.metadata_path)
            metadata = c.get_quick(self.cfg.metadata_path, max_length=1024, path_type='json')

            # This will set the time to GMT, not localtime
            self.set_alarm(c.last_fetch_time, metadata)

            self.feed_wdt()
            del metadata
            del battery
            self.log("Fetching image from " + self.cfg.image_path)
            self.epd.image_erase_frame_buffer()
            self.feed_wdt()

            length, socket = c.get_object(self.cfg.image_path)

            if length != 15016:
                raise ValueError("Wrong data size for image: %d" % length)

            self.feed_wdt()

        except (RuntimeError, ValueError, OSError) as e:
            self.log("Failed to get remote info: " + str(e))
            self.display_cannot_connect()
            self.rtc.alarm(time=3600000)
            return

        sleep_ms(1000) # How do we make the write to display more reliable?
        self.feed_wdt()
        self.log("Uploading to display")
        self.display_file_image(socket)
        c.get_object_done() # close off socket

        if self.cfg.src == "sd":
            # If we've got a working config from SD instead of flash
            self.log("Transferring working config")
            Config.transfer()
            self.log("SUCCESS")

        self.log("Finished. Mem free: %d" % gc.mem_free())
