
import struct
import time
import machine
from machine import SPI, Pin
from binascii import hexlify


class EPD(object):
    MAX_READ = 45
    SW_NORMAL_PROCESSING = 0x9000
    EP_FRAMEBUFFER_SLOT_OVERRUN = 0x6a84 # too much data fed in
    EP_SW_INVALID_LE = 0x6c00 # Wrong expected length
    EP_SW_INSTRUCTION_NOT_SUPPORTED = 0x6d00 # bad instr
    EP_SW_WRONG_PARAMETERS_P1P2 = 0x6a00
    EP_SW_WRONG_LENGTH = 0x6700

    DEFAULT_SLOT=0 # always the *oldest*, should wear-level then I think

    def __init__(self, debug=False, baud=100000):
        # From datasheet
        # Bit rate – up to 12 MHz1
        # ▪ Polarity – CPOL = 1; clock transition high-to-low on the leading edge and low-to-high on the
        #   trailing edge
        # ▪ Phase – CPHA = 1; setup on the leading edge and sample on the trailing edge
        # ▪ Bit order – MSB first
        # ▪ Chip select polarity – active low
        self.spi = SPI(0)
        try:
            self.spi.init(mode=SPI.MASTER, baudrate=baud, bits=8,
                          polarity=1, phase=1, firstbit=SPI.MSB,
                          pins=('GP31', 'GP16', 'GP30')) # CLK, MOSI, MISO
        except AttributeError:
            self.spi.init(baudrate=baud, bits=8,
                          polarity=1, phase=1, firstbit=SPI.MSB,
                          pins=('GP31', 'GP16', 'GP30')) # CLK, MOSI, MISO

        # These are all active low!
        self.tc_en_bar = Pin('GP4', mode=Pin.OUT)

        self.disable()

        self.tc_busy_bar = Pin('GP5', mode=Pin.IN)
        self.tc_busy_bar.irq(trigger=Pin.IRQ_RISING) # Wake up when it changes
        self.tc_cs_bar = Pin('GP17', mode=Pin.ALT, alt=7)

        self.debug = debug

    def enable(self):
        self.tc_en_bar.value(0) # Power up
        time.sleep_ms(5)
        while self.tc_busy_bar() == 0:
            machine.idle() # will it wake up here?
        # /tc_busy goes high during startup, low during init, then high when not busy

    def disable(self):
        self.tc_en_bar.value(1) # Off

    def send_command(self, ins, p1, p2, data=None, expected=None):

        # These command variables are always sent
        cmd = struct.pack('3B', ins, p1, p2)

        # Looks like data is only sent with the length (Lc)
        if data:
            assert len(data) <= 251 # Thus speaks the datasheet
            cmd += struct.pack('B', len(data))
            cmd += data

        # Expected data is either not present at all, 0 for null-terminated, or a number for fixed
        if expected is not None:
            cmd += struct.pack('B', expected)

        if self.debug:
            print("Sending: " + hexlify(cmd).decode())

        self.spi.write(cmd)

        # Wait for a little while
        time.sleep_us(15) # This should take at most 14.5us
        while self.tc_busy_bar() == 0:
            machine.idle()

        # Request a response
        if expected is not None:
            if expected > 0:
                result_bytes = self.spi.read(2 + expected)
            else:
                result_bytes = self.spi.read(EPD.MAX_READ)
                strlen = result_bytes.find(b'\x00')
                result_bytes = result_bytes[:strlen] + result_bytes[strlen+1:strlen+3]
        else:
            result_bytes = self.spi.read(2)

        if self.debug:
            print("Received: " + hexlify(result_bytes).decode())

        (result,) = struct.unpack_from('>H', result_bytes[-2:])

        if result != EPD.SW_NORMAL_PROCESSING:
            raise ValueError("Bad result code: 0x%x" % result)

        return result_bytes[:-2]

    @staticmethod
    def calculate_checksum(data, skip=16):
        """
        Initial checksum value is 0x6363

        :param data:
        :param skip: Skip some data as slices are expensive
        :return:
        """
        acc = 0x6363
        for byte in data:
            if skip > 0:
                skip -= 1
            else:
                acc ^= byte
                acc = ((acc >> 8) | (acc << 8)) & 0xffff
                acc ^= ((acc & 0xff00) << 4) & 0xffff
                acc ^= (acc >> 8) >> 4
                acc ^= (acc & 0xff00) >> 5
        return acc

    def get_sensor_data(self):
        # GetSensorData
        val = self.send_command(0xe5, 1, 0, expected=2)
        (temp,) = struct.unpack(">H", val)
        return temp

    def get_device_id(self):
        return self.send_command(0x30, 2, 1, expected=0x14)

    def get_system_info(self):
        return self.send_command(0x31, 1, 1, expected=0)

    def get_system_version_code(self):
        return self.send_command(0x31, 2, 1, expected=0x10)

    def display_update(self, slot=0, flash=True):
        cmd = 0x86
        if flash:
            cmd = 0x24
        self.send_command(cmd, 1, slot)

    def reset_data_pointer(self):
        self.send_command(0x20, 0xd, 0)

    def image_erase_frame_buffer(self, slot=0):
        self.send_command(0x20, 0xe, slot)

    def get_checksum(self, slot):
        cksum_val = self.send_command(0x2e, 1, slot, expected=2)
        (cksum,) = struct.unpack(">H", cksum_val)
        return cksum

    def upload_image_data(self, data, slot=0, delay_us=1000):
        self.send_command(0x20, 1, slot, data)
        time.sleep_us(delay_us)

    def upload_whole_image(self, img, slot=0):
        """
        Chop up chunks and send it
        :param img: Image to send in EPD format
        :param slot: Slot framebuffer number to use
        :param delay_us: Delay between packets? 450us and the Tbusy line never comes back
        :return:
        """
        total = len(img)
        idx = 0
        try:
            while idx < total - 250:
                chunk = img[idx:idx+250]
                self.upload_image_data(chunk, slot)
                del chunk
                idx += 250
            self.upload_image_data(img[idx:], slot)
        except KeyboardInterrupt:
            print("Stopped at user request at position: %d (%d)" % (idx, (idx // 250)))
        except ValueError as e:
            print("Stopped at position: %d (%d) - %s" % (idx, (idx // 250), e))
