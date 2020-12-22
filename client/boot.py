# boot.py -- run on boot-up
# can run arbitrary Python, but best to keep it minimal
from machine import UART
from os import dupterm

uart = UART(0, 115200)
dupterm(uart)
print('UART up')
