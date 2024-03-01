from bme import *
from machine import I2C, Pin
import time
bme = BME680_I2C(I2C(-1, Pin(44), Pin(43)))

for _ in range(3):
    print(bme.temperature, bme.humidity, bme.pressure, bme.gas)
    time.sleep(1)
