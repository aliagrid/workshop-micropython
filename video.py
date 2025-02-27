"""
Manually Statically compiled optimized code for MicroPython MLX90640 and ESP32-C3 and urequests
"""
import machine, network  # type: ignore
import math
import struct
import micropython, time, gc
from micropython import const# Some libraries that we will use
import time
import json
import array


print("Beginning ...")

#wifi_keys = secrets.get_wifi_keys()
#wifi_known_names = list(wifi_keys.keys())
#wifi_known_passs = list(wifi_keys.values())
#firebase_url_endpoint = secrets.get_firebase_endpoint()
#wlan = network.WLAN(network.STA_IF)
#wlan.active(True)
#class wifi:
#  def scan(self):
#      try:
#        return wlan.scan()
#      except RuntimeError as exc:
#        print(f"{exc}\nNo wifi access points found :(")
#        raise exc

#  def networkInScan(self, __scan):
#      print("network names known: ", wifi_known_names)
#      for s in __scan:
#          detected_name = s[0]
#          # print(f"Checking if {detected_name}")
#          if detected_name in wifi_known_names:
#              return True, wifi_known_names.index(detected_name)
#      return False, -1

#  def scanNetworks(self, ):
#      return self.networkInScan(self.scan())

#  def plsConnect(self, ):
#      can, index = self.scanNetworks()
#      if not can:
#          print('Could not find any known networks :(')
#          print(f"{self.scan()=}")
#          wlan.active(False)
#          time.sleep(5)
#          wlan.active(True)
#          return False
#      else:
#          # print(f"{index=}")
#          wifi_name = wifi_known_names[index]
#          wifi_pass = wifi_known_passs[index]
#          if type(wifi_pass) is not tuple:
#              # print(f'Found wifi: {wifi_name}; Connecting with password: {wifi_pass}')
#              print(f'Found wifi: {wifi_name}; Connecting;')
#              wlan.connect(wifi_name, wifi_pass)
#              # print('Connecting... _')
#              tryNum = 0
#              while not wlan.isconnected() and tryNum < 20:
#                  tryNum += 10
#                  time.sleep(10)
#                  print(f"Connecting ... {str(tryNum)} seconds ...")
#
#              return self.isGood(False)
#          elif type(wifi_pass) is tuple:
#              print(
#                  f"Found WPA2 Enterprise wifi: {wifi_name}; Connecting with username: {wifi_pass[0]}")
#              wlan.connect(wifi_name, authmode=network.AUTH_WPA2_ENT,
#                          username=wifi_pass[0], password=wifi_pass[1])


#  def isGood(self, getGood=False):
#      if getGood:
#          self.plsConnect()
#      return wlan.isconnected()


#  def getGoodWIFI(self, ):
#      # plsConnect()
#      while not self.isGood():
#          print("Top level attempting WIFI connect ...")
#          self.plsConnect()
#          time.sleep(1)
#      print(f"Got good wifi: {wlan.ifconfig()}")


#  def printStatus(self, ):
#      print(f"Got good wifi: {wlan.ifconfig()}")

eeData = [0] * const(832)
I2C_READ_LEN = const(2048)
SCALEALPHA = const(0.000001)
MLX90640_DEVICEID1 = const(0x2407)
OPENAIR_TA_SHIFT = const(8)

class RefreshRate:  # pylint: disable=too-few-public-methods
    """ Enum-like class for MLX90640's refresh rate """

    REFRESH_0_5_HZ = const(0b000)  # 0.5Hz
    REFRESH_1_HZ = const(0b001)  # 1Hz
    REFRESH_2_HZ = const(0b010) # 2Hz
    REFRESH_4_HZ = const(0b011)  # 4Hz
    REFRESH_8_HZ = const(0b100)  # 8Hz
    REFRESH_16_HZ = const(0b101)  # 16Hz
    REFRESH_32_HZ = const(0b110)  # 32Hz
    REFRESH_64_HZ = const(0b111)  # 64Hz

class ContextManaged:
    """An object that automatically deinitializes hardware with a context manager."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.deinit()

    # pylint: disable=no-self-use
    def deinit(self):
        """Free any hardware used by the object."""
        return

class Lockable(ContextManaged):
    """An object that must be locked to prevent collisions on a microcontroller resource."""

    _locked = False

    def try_lock(self):
        """Attempt to grab the lock. Return True on success, False if the lock is already taken."""
        if self._locked:
            return False
        self._locked = True
        return True

    def unlock(self):
        """Release the lock so others may use the resource."""
        if self._locked:
            self._locked = False
        else:
            raise ValueError("Not locked")

class I2C(Lockable):
    def __init__(self, pins=(21, 22), frequency=100000):
        self.init(pins, frequency)

    def init(self, pins, frequency):
        self.deinit()
        self._pins = (machine.Pin(int(pins[0])), machine.Pin(int(pins[1])))

        try:
            #_newI2C = _I2C(0, scl=machine.Pin(21), sda=machine.Pin(22))
            #print(f"new i2c: {_newI2C=}")
            #self._i2c = _newI2C
            #print(f"Self._i2c after: {self._i2c=}")
            self._i2c = machine.I2C(0, scl=self._pins[0], sda=self._pins[1], freq=frequency)
        except RuntimeError:
            raise
        print(f"Created i2c: {self._i2c}")

    def deinit(self):
        try:
            del self._i2c
        except AttributeError:
            pass

    def scan(self):
        return self._i2c.scan()

    def readfrom_into(self, address, buffer, *, start=0, end=None):
        if start is not 0 or end is not None:
            if end is None:
                end = len(buffer)
            buffer = memoryview(buffer)[start:end]
        stop = True  # remove for efficiency later
        return self._i2c.readfrom_into(address, buffer)

    def writeto(self, address, buffer, *, start=0, end=None, stop=True):
        if isinstance(buffer, str):
            buffer = bytes([ord(x) for x in buffer])
        if start is not 0 or end is not None:
            if end is None:
                return self._i2c.writeto(address, memoryview(buffer)[start:], stop)
            else:
                return self._i2c.writeto(address, memoryview(buffer)[start:end], stop)
        return self._i2c.writeto(address, buffer, stop)

class I2CDevice:
    def __init__(self, i2c, device_address, probe=True):
        self.i2c = i2c
        self._has_write_read = False # hasattr(self.i2c, "writeto_then_readfrom") --> has been turned to False
        self.device_address = device_address

        if probe:
            self.__probe_for_device()

    def readinto(self, buf, *, start=0, end=None):
        if end is None:
            end = len(buf)
        self.i2c.readfrom_into(self.device_address, buf, start=start, end=end)

    def write(self, buf, *, start=0, end=None, stop=True):
        if end is None:
            end = len(buf)
        self.i2c.writeto(self.device_address, buf, start=start, end=end, stop=stop)

    # pylint: disable-msg=too-many-arguments
    def write_then_readinto(
        self,
        out_buffer,
        in_buffer,
        *,
        out_start=0,
        out_end=None,
        in_start=0,
        in_end=None,
        stop=False
    ):
        if out_end is None:
            out_end = len(out_buffer)
        if in_end is None:
            in_end = len(in_buffer)
        if stop:
            raise ValueError("Stop must be False. Use writeto instead.")
        if self._has_write_read:
            #print("c",dir(self.i2c))
            # In linux, at least, this is a special kernel function call
            self.i2c.writeto_then_readfrom(
                self.device_address,
                out_buffer,
                in_buffer,
                out_start=out_start,
                out_end=out_end,
                in_start=in_start,
                in_end=in_end,
            )

        else:
            # If we don't have a special implementation, we can fake it with two calls
            self.i2c.writeto(self.device_address, out_buffer, stop=False) # These lines have been changed to make it work with wipy micropython I2C module
            #self.write(out_buffer, start=out_start, end=out_end, stop=False)
            #self.readinto(in_buffer, start=in_start, end=in_end)
            self.i2c.readfrom_into(self.device_address, in_buffer) # These lines have been changed to make it work with wipy micropython I2C module


    # pylint: enable-msg=too-many-arguments

    def __enter__(self):
        while not self.i2c.try_lock():
            pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.i2c.unlock()
        return False

    def __probe_for_device(self):
        """
        Try to read a byte from an address,
        if you get an OSError it means the device is not there
        or that the device does not support these means of probing
        """
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.writeto(self.device_address, b"")
        except OSError:
            # some OS's dont like writing an empty bytesting...
            # Retry by reading a byte
            try:
                result = bytearray(1)
                self.i2c.readfrom_into(self.device_address, result)
            except OSError:
                raise ValueError("No I2C device at address: %x" % self.device_address)
        finally:
            self.i2c.unlock()

class MLX90640:  # pylint: disable=too-many-instance-attributes
    """Interface to the MLX90640 temperature sensor."""

    kVdd = 0
    vdd25 = 0
    KvPTAT = 0
    KtPTAT = 0
    vPTAT25 = 0
    alphaPTAT = 0
    gainEE = 0
    tgc = 0
    KsTa = 0
    resolutionEE = 0
    calibrationModeEE = 0
    ksTo = [0] * 5
    ct = [0] * 5
    alpha = [0] * 768
    alphaScale = 0
    offset = [0] * 768
    kta = [0] * 768
    ktaScale = 0
    kv = [0] * 768
    kvScale = 0
    cpAlpha = [0] * 2
    cpOffset = [0] * 2
    ilChessC = [0] * 3
    brokenPixels = [0xFFFF] * 5
    outlierPixels = [0xFFFF] * 5
    cpKta = 0
    cpKv = 0

    def __init__(self, i2c_bus, address=0x33):
        self.i2c_device = I2CDevice(i2c_bus, address)
        self._I2CReadWords(0x2400, eeData)
        # print(eeData)
        self._ExtractParameters()

    @property
    def serial_number(self):
        """ 3-item tuple of hex values that are unique to each MLX90640 """
        serialWords = [0, 0, 0]
        self._I2CReadWords(MLX90640_DEVICEID1, serialWords)
        return serialWords

    @property
    def refresh_rate(self):
        """ How fast the MLX90640 will spit out data. Start at lowest speed in
        RefreshRate and then slowly increase I2C clock rate and rate until you
        max out. The sensor does not like it if the I2C host cannot 'keep up'!"""
        controlRegister = [0]
        self._I2CReadWords(0x800D, controlRegister)
        return (controlRegister[0] >> 7) & 0x07

    @refresh_rate.setter
    def refresh_rate(self, rate):
        controlRegister = [0]
        value = (rate & 0x7) << 7
        self._I2CReadWords(0x800D, controlRegister)
        value |= controlRegister[0] & 0xFC7F
        self._I2CWriteWord(0x800D, value)

    def getFrame(self, framebuf, index):
        """ Request both 'halves' of a frame from the sensor, merge them
        and calculate the temperature in C for each of 32x24 pixels. Placed
        into the 768-element array passed in! """
        emissivity = 0.95
        tr = 23.15
        mlx90640Frame = [0] * 834

        for x in range(2):
            status = self._GetFrameData(mlx90640Frame)
            if status < 0:
                raise RuntimeError("Frame data error")

            #if x == 1:
            #    with open(f'raw-{index}.txt', 'w') as file:
            #        file.write(','.join(map(str, mlx90640Frame[:768])))

            # For a MLX90640 in the open air the shift is -8 degC.
            tr = self._GetTa(mlx90640Frame) - OPENAIR_TA_SHIFT
            self._CalculateTo(mlx90640Frame, emissivity, tr, framebuf)

    def _GetFrameData(self, frameData):
        dataReady = 0
        cnt = 0
        statusRegister = [0]
        controlRegister = [0]

        while dataReady == 0:
            self._I2CReadWords(0x8000, statusRegister)
            dataReady = statusRegister[0] & 0x0008
            # print("ready status: 0x%x" % dataReady)

        while (dataReady != 0) and (cnt < 5):
            self._I2CWriteWord(0x8000, 0x0030)
            # print("Read frame", cnt)
            self._I2CReadWords(0x0400, frameData, end=832)

            self._I2CReadWords(0x8000, statusRegister)
            dataReady = statusRegister[0] & 0x0008
            # print("frame ready: 0x%x" % dataReady)
            cnt += 1

        if cnt > 4:
            raise RuntimeError("Too many retries")

        self._I2CReadWords(0x800D, controlRegister)
        frameData[832] = controlRegister[0]
        frameData[833] = statusRegister[0] & 0x0001
        return frameData[833]

    def _GetTa(self, frameData):
        vdd = self._GetVdd(frameData)

        ptat = frameData[800]
        if ptat > 32767:
            ptat -= 65536

        ptatArt = frameData[768]
        if ptatArt > 32767:
            ptatArt -= 65536
        ptatArt = (ptat / (ptat * self.alphaPTAT + ptatArt)) * math.pow(2, 18)

        ta = ptatArt / (1 + self.KvPTAT * (vdd - 3.3)) - self.vPTAT25
        ta = ta / self.KtPTAT + 25
        return ta

    def _GetVdd(self, frameData):
        vdd = frameData[810]
        if vdd > 32767:
            vdd -= 65536

        resolutionRAM = (frameData[832] & 0x0C00) >> 10
        resolutionCorrection = math.pow(2, self.resolutionEE) / math.pow(
            2, resolutionRAM
        )
        vdd = (resolutionCorrection * vdd - self.vdd25) / self.kVdd + 3.3

        return vdd

    def _CalculateTo(self, frameData, emissivity, tr, result):
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        subPage = frameData[833]
        alphaCorrR = [0] * 4
        irDataCP = [0, 0]

        vdd = self._GetVdd(frameData)
        ta = self._GetTa(frameData)

        ta4 = ta + 273.15
        ta4 = ta4 * ta4
        ta4 = ta4 * ta4
        tr4 = tr + 273.15
        tr4 = tr4 * tr4
        tr4 = tr4 * tr4
        taTr = tr4 - (tr4 - ta4) / emissivity

        ktaScale = math.pow(2, self.ktaScale)
        kvScale = math.pow(2, self.kvScale)
        alphaScale = math.pow(2, self.alphaScale)

        alphaCorrR[0] = 1 / (1 + self.ksTo[0] * 40)
        alphaCorrR[1] = 1
        alphaCorrR[2] = 1 + self.ksTo[1] * self.ct[2]
        alphaCorrR[3] = alphaCorrR[2] * (1 + self.ksTo[2] * (self.ct[3] - self.ct[2]))

        # --------- Gain calculation -----------------------------------
        gain = frameData[778]
        if gain > 32767:
            gain -= 65536
        gain = self.gainEE / gain

        # --------- To calculation -------------------------------------
        mode = (frameData[832] & 0x1000) >> 5

        irDataCP[0] = frameData[776]
        irDataCP[1] = frameData[808]
        for i in range(2):
            if irDataCP[i] > 32767:
                irDataCP[i] -= 65536
            irDataCP[i] *= gain

        irDataCP[0] -= (
            self.cpOffset[0]
            * (1 + self.cpKta * (ta - 25))
            * (1 + self.cpKv * (vdd - 3.3))
        )
        if mode == self.calibrationModeEE:
            irDataCP[1] -= (
                self.cpOffset[1]
                * (1 + self.cpKta * (ta - 25))
                * (1 + self.cpKv * (vdd - 3.3))
            )
        else:
            irDataCP[1] -= (
                (self.cpOffset[1] + self.ilChessC[0])
                * (1 + self.cpKta * (ta - 25))
                * (1 + self.cpKv * (vdd - 3.3))
            )

        for pixelNumber in range(768):
            ilPattern = pixelNumber // 32 - (pixelNumber // 64) * 2
            chessPattern = ilPattern ^ (pixelNumber - (pixelNumber // 2) * 2)
            conversionPattern = (
                (pixelNumber + 2) // 4
                - (pixelNumber + 3) // 4
                + (pixelNumber + 1) // 4
                - pixelNumber // 4
            ) * (1 - 2 * ilPattern)

            if mode == 0:
                pattern = ilPattern
            else:
                pattern = chessPattern

            if pattern == frameData[833]:
                irData = frameData[pixelNumber]
                if irData > 32767:
                    irData -= 65536
                irData *= gain

                kta = self.kta[pixelNumber] / ktaScale
                kv = self.kv[pixelNumber] / kvScale
                irData -= (
                    self.offset[pixelNumber]
                    * (1 + kta * (ta - 25))
                    * (1 + kv * (vdd - 3.3))
                )

                if mode != self.calibrationModeEE:
                    irData += (
                        self.ilChessC[2] * (2 * ilPattern - 1)
                        - self.ilChessC[1] * conversionPattern
                    )

                irData = irData - self.tgc * irDataCP[subPage]
                irData /= emissivity

                alphaCompensated = SCALEALPHA * alphaScale / self.alpha[pixelNumber]
                alphaCompensated *= 1 + self.KsTa * (ta - 25)

                Sx = (
                    alphaCompensated
                    * alphaCompensated
                    * alphaCompensated
                    * (irData + alphaCompensated * taTr)
                )
                Sx = math.sqrt(math.sqrt(Sx)) * self.ksTo[1]

                To = (
                    math.sqrt(
                        math.sqrt(
                            irData
                            / (alphaCompensated * (1 - self.ksTo[1] * 273.15) + Sx)
                            + taTr
                        )
                    )
                    - 273.15
                )

                if To < self.ct[1]:
                    torange = 0
                elif To < self.ct[2]:
                    torange = 1
                elif To < self.ct[3]:
                    torange = 2
                else:
                    torange = 3

                To = (
                    math.sqrt(
                        math.sqrt(
                            irData
                            / (
                                alphaCompensated
                                * alphaCorrR[torange]
                                * (1 + self.ksTo[torange] * (To - self.ct[torange]))
                            )
                            + taTr
                        )
                    )
                    - 273.15
                )

                result[pixelNumber] = To

    # pylint: enable=too-many-locals, too-many-branches, too-many-statements

    def _ExtractParameters(self):
        self._ExtractVDDParameters()
        self._ExtractPTATParameters()
        self._ExtractGainParameters()
        self._ExtractTgcParameters()
        self._ExtractResolutionParameters()
        self._ExtractKsTaParameters()
        self._ExtractKsToParameters()
        self._ExtractCPParameters()
        self._ExtractAlphaParameters()
        self._ExtractOffsetParameters()
        self._ExtractKtaPixelParameters()
        self._ExtractKvPixelParameters()
        self._ExtractCILCParameters()
        self._ExtractDeviatingPixels()

    def _ExtractVDDParameters(self):
        # extract VDD
        self.kVdd = (eeData[51] & 0xFF00) >> 8
        if self.kVdd > 127:
            self.kVdd -= 256  # convert to signed
        self.kVdd *= 32
        self.vdd25 = eeData[51] & 0x00FF
        self.vdd25 = ((self.vdd25 - 256) << 5) - 8192

    def _ExtractPTATParameters(self):
        # extract PTAT
        self.KvPTAT = (eeData[50] & 0xFC00) >> 10
        if self.KvPTAT > 31:
            self.KvPTAT -= 64
        self.KvPTAT /= 4096
        self.KtPTAT = eeData[50] & 0x03FF
        if self.KtPTAT > 511:
            self.KtPTAT -= 1024
        self.KtPTAT /= 8
        self.vPTAT25 = eeData[49]
        self.alphaPTAT = (eeData[16] & 0xF000) / math.pow(2, 14) + 8

    def _ExtractGainParameters(self):
        # extract Gain
        self.gainEE = eeData[48]
        if self.gainEE > 32767:
            self.gainEE -= 65536

    def _ExtractTgcParameters(self):
        # extract Tgc
        #print(eeData[60])
        self.tgc = eeData[60] & 0x00FF
        #print(self.tgc)
        if self.tgc > 127:
            self.tgc -= 256
        self.tgc /= 32
        #print(self.tgc)

    def _ExtractResolutionParameters(self):
        # extract resolution
        self.resolutionEE = (eeData[56] & 0x3000) >> 12

    def _ExtractKsTaParameters(self):
        # extract KsTa
        self.KsTa = (eeData[60] & 0xFF00) >> 8
        if self.KsTa > 127:
            self.KsTa -= 256
        self.KsTa /= 8192

    def _ExtractKsToParameters(self):
        # extract ksTo
        step = ((eeData[63] & 0x3000) >> 12) * 10
        self.ct[0] = -40
        self.ct[1] = 0
        self.ct[2] = (eeData[63] & 0x00F0) >> 4
        self.ct[3] = (eeData[63] & 0x0F00) >> 8
        self.ct[2] *= step
        self.ct[3] = self.ct[2] + self.ct[3] * step

        KsToScale = (eeData[63] & 0x000F) + 8
        KsToScale = 1 << KsToScale

        self.ksTo[0] = eeData[61] & 0x00FF
        self.ksTo[1] = (eeData[61] & 0xFF00) >> 8
        self.ksTo[2] = eeData[62] & 0x00FF
        self.ksTo[3] = (eeData[62] & 0xFF00) >> 8

        for i in range(4):
            if self.ksTo[i] > 127:
                self.ksTo[i] -= 256
            self.ksTo[i] /= KsToScale
        self.ksTo[4] = -0.0002

    def _ExtractCPParameters(self):
        # extract CP
        offsetSP = [0] * 2
        alphaSP = [0] * 2

        alphaScale = ((eeData[32] & 0xF000) >> 12) + 27

        offsetSP[0] = eeData[58] & 0x03FF
        if offsetSP[0] > 511:
            offsetSP[0] -= 1024

        offsetSP[1] = (eeData[58] & 0xFC00) >> 10
        if offsetSP[1] > 31:
            offsetSP[1] -= 64
        offsetSP[1] += offsetSP[0]

        alphaSP[0] = eeData[57] & 0x03FF
        if alphaSP[0] > 511:
            alphaSP[0] -= 1024
        alphaSP[0] /= math.pow(2, alphaScale)

        alphaSP[1] = (eeData[57] & 0xFC00) >> 10
        if alphaSP[1] > 31:
            alphaSP[1] -= 64
        alphaSP[1] = (1 + alphaSP[1] / 128) * alphaSP[0]

        cpKta = eeData[59] & 0x00FF
        if cpKta > 127:
            cpKta -= 256
        ktaScale1 = ((eeData[56] & 0x00F0) >> 4) + 8
        self.cpKta = cpKta / math.pow(2, ktaScale1)

        cpKv = (eeData[59] & 0xFF00) >> 8
        if cpKv > 127:
            cpKv -= 256
        kvScale = (eeData[56] & 0x0F00) >> 8
        self.cpKv = cpKv / math.pow(2, kvScale)

        self.cpAlpha[0] = alphaSP[0]
        self.cpAlpha[1] = alphaSP[1]
        self.cpOffset[0] = offsetSP[0]
        self.cpOffset[1] = offsetSP[1]
        #print(self.cpAlpha[0])
        #print(self.cpAlpha[1])

    def _ExtractAlphaParameters(self):
        # extract alpha
        accRemScale = eeData[32] & 0x000F
        accColumnScale = (eeData[32] & 0x00F0) >> 4
        accRowScale = (eeData[32] & 0x0F00) >> 8
        alphaScale = ((eeData[32] & 0xF000) >> 12) + 30
        alphaRef = eeData[33]
        accRow = [0] * 24
        accColumn = [0] * 32
        alphaTemp = [0] * 768

        for i in range(6):
            p = i * 4
            accRow[p + 0] = eeData[34 + i] & 0x000F
            accRow[p + 1] = (eeData[34 + i] & 0x00F0) >> 4
            accRow[p + 2] = (eeData[34 + i] & 0x0F00) >> 8
            accRow[p + 3] = (eeData[34 + i] & 0xF000) >> 12

        for i in range(24):
            if accRow[i] > 7:
                accRow[i] -= 16

        for i in range(8):
            p = i * 4
            accColumn[p + 0] = eeData[40 + i] & 0x000F
            accColumn[p + 1] = (eeData[40 + i] & 0x00F0) >> 4
            accColumn[p + 2] = (eeData[40 + i] & 0x0F00) >> 8
            accColumn[p + 3] = (eeData[40 + i] & 0xF000) >> 12

        for i in range(32):
            if accColumn[i] > 7:
                accColumn[i] -= 16
        for i in range(24):
            for j in range(32):
                p = 32 * i + j
                alphaTemp[p] = (eeData[64 + p] & 0x03F0) >> 4
                if alphaTemp[p] > 31:
                    alphaTemp[p] -= 64
                alphaTemp[p] *= 1 << accRemScale
                alphaTemp[p] += (
                    alphaRef
                    + (accRow[i] << accRowScale)
                    + (accColumn[j] << accColumnScale)
                )
                alphaTemp[p] /= math.pow(2, alphaScale)
                alphaTemp[p] -= self.tgc * (self.cpAlpha[0] + self.cpAlpha[1]) / 2
                alphaTemp[p] = SCALEALPHA / alphaTemp[p]
        # print("alphaTemp: ", alphaTemp)

        temp = max(alphaTemp)
        #print("temp", temp)

        alphaScale = 0
        while temp < 32768:
            temp *= 2
            alphaScale += 1

        for i in range(768):
            temp = alphaTemp[i] * math.pow(2, alphaScale)
            self.alpha[i] = int(temp + 0.5)

        self.alphaScale = alphaScale

    def _ExtractOffsetParameters(self):
        # extract offset
        occRow = [0] * 24
        occColumn = [0] * 32

        occRemScale = eeData[16] & 0x000F
        occColumnScale = (eeData[16] & 0x00F0) >> 4
        occRowScale = (eeData[16] & 0x0F00) >> 8
        offsetRef = eeData[17]
        if offsetRef > 32767:
            offsetRef -= 65536

        for i in range(6):
            p = i * 4
            occRow[p + 0] = eeData[18 + i] & 0x000F
            occRow[p + 1] = (eeData[18 + i] & 0x00F0) >> 4
            occRow[p + 2] = (eeData[18 + i] & 0x0F00) >> 8
            occRow[p + 3] = (eeData[18 + i] & 0xF000) >> 12

        for i in range(24):
            if occRow[i] > 7:
                occRow[i] -= 16

        for i in range(8):
            p = i * 4
            occColumn[p + 0] = eeData[24 + i] & 0x000F
            occColumn[p + 1] = (eeData[24 + i] & 0x00F0) >> 4
            occColumn[p + 2] = (eeData[24 + i] & 0x0F00) >> 8
            occColumn[p + 3] = (eeData[24 + i] & 0xF000) >> 12

        for i in range(32):
            if occColumn[i] > 7:
                occColumn[i] -= 16

        for i in range(24):
            for j in range(32):
                p = 32 * i + j
                self.offset[p] = (eeData[64 + p] & 0xFC00) >> 10
                if self.offset[p] > 31:
                    self.offset[p] -= 64
                self.offset[p] *= 1 << occRemScale
                self.offset[p] += (
                    offsetRef
                    + (occRow[i] << occRowScale)
                    + (occColumn[j] << occColumnScale)
                )

    def _ExtractKtaPixelParameters(self):  # pylint: disable=too-many-locals
        # extract KtaPixel
        KtaRC = [0] * 4
        ktaTemp = [0] * 768

        KtaRoCo = (eeData[54] & 0xFF00) >> 8
        if KtaRoCo > 127:
            KtaRoCo -= 256
        KtaRC[0] = KtaRoCo

        KtaReCo = eeData[54] & 0x00FF
        if KtaReCo > 127:
            KtaReCo -= 256
        KtaRC[2] = KtaReCo

        KtaRoCe = (eeData[55] & 0xFF00) >> 8
        if KtaRoCe > 127:
            KtaRoCe -= 256
        KtaRC[1] = KtaRoCe

        KtaReCe = eeData[55] & 0x00FF
        if KtaReCe > 127:
            KtaReCe -= 256
        KtaRC[3] = KtaReCe

        ktaScale1 = ((eeData[56] & 0x00F0) >> 4) + 8
        ktaScale2 = eeData[56] & 0x000F

        for i in range(24):
            for j in range(32):
                p = 32 * i + j
                split = 2 * (p // 32 - (p // 64) * 2) + p % 2
                ktaTemp[p] = (eeData[64 + p] & 0x000E) >> 1
                if ktaTemp[p] > 3:
                    ktaTemp[p] -= 8
                ktaTemp[p] *= 1 << ktaScale2
                ktaTemp[p] += KtaRC[split]
                ktaTemp[p] /= math.pow(2, ktaScale1)
                # ktaTemp[p] = ktaTemp[p] * mlx90640->offset[p];

        temp = abs(ktaTemp[0])
        for kta in ktaTemp:
            temp = max(temp, abs(kta))

        ktaScale1 = 0
        while temp < 64:
            temp *= 2
            ktaScale1 += 1

        for i in range(768):
            temp = ktaTemp[i] * math.pow(2, ktaScale1)
            if temp < 0:
                self.kta[i] = int(temp - 0.5)
            else:
                self.kta[i] = int(temp + 0.5)
        self.ktaScale = ktaScale1

    def _ExtractKvPixelParameters(self):
        KvT = [0] * 4
        kvTemp = [0] * 768

        KvRoCo = (eeData[52] & 0xF000) >> 12
        if KvRoCo > 7:
            KvRoCo -= 16
        KvT[0] = KvRoCo

        KvReCo = (eeData[52] & 0x0F00) >> 8
        if KvReCo > 7:
            KvReCo -= 16
        KvT[2] = KvReCo

        KvRoCe = (eeData[52] & 0x00F0) >> 4
        if KvRoCe > 7:
            KvRoCe -= 16
        KvT[1] = KvRoCe

        KvReCe = eeData[52] & 0x000F
        if KvReCe > 7:
            KvReCe -= 16
        KvT[3] = KvReCe

        kvScale = (eeData[56] & 0x0F00) >> 8

        for i in range(24):
            for j in range(32):
                p = 32 * i + j
                split = 2 * (p // 32 - (p // 64) * 2) + p % 2
                kvTemp[p] = KvT[split]
                kvTemp[p] /= math.pow(2, kvScale)
                # kvTemp[p] = kvTemp[p] * mlx90640->offset[p];

        temp = abs(kvTemp[0])
        for kv in kvTemp:
            temp = max(temp, abs(kv))

        kvScale = 0
        while temp < 64:
            temp *= 2
            kvScale += 1

        for i in range(768):
            temp = kvTemp[i] * math.pow(2, kvScale)
            if temp < 0:
                self.kv[i] = int(temp - 0.5)
            else:
                self.kv[i] = int(temp + 0.5)
        self.kvScale = kvScale

    def _ExtractCILCParameters(self):
        ilChessC = [0] * 3

        self.calibrationModeEE = (eeData[10] & 0x0800) >> 4
        self.calibrationModeEE = self.calibrationModeEE ^ 0x80

        ilChessC[0] = eeData[53] & 0x003F
        if ilChessC[0] > 31:
            ilChessC[0] -= 64
        ilChessC[0] /= 16.0

        ilChessC[1] = (eeData[53] & 0x07C0) >> 6
        if ilChessC[1] > 15:
            ilChessC[1] -= 32
        ilChessC[1] /= 2.0

        ilChessC[2] = (eeData[53] & 0xF800) >> 11
        if ilChessC[2] > 15:
            ilChessC[2] -= 32
        ilChessC[2] /= 8.0

        self.ilChessC = ilChessC

    def _ExtractDeviatingPixels(self):
        self.brokenPixels = [0xFFFF] * 5
        self.outlierPixels = [0xFFFF] * 5

        pixCnt = 0
        brokenPixCnt = 0
        outlierPixCnt = 0

        while (pixCnt < 768) and (brokenPixCnt < 5) and (outlierPixCnt < 5):
            if eeData[pixCnt + 64] == 0:
                self.brokenPixels[brokenPixCnt] = pixCnt
                brokenPixCnt += 1
            elif (eeData[pixCnt + 64] & 0x0001) != 0:
                self.outlierPixels[outlierPixCnt] = pixCnt
                outlierPixCnt += 1
            pixCnt += 1

        if brokenPixCnt > 4:
            raise RuntimeError("More than 4 broken pixels")
        if outlierPixCnt > 4:
            raise RuntimeError("More than 4 outlier pixels")
        if (brokenPixCnt + outlierPixCnt) > 4:
            raise RuntimeError("More than 4 faulty pixels")
        # print("Found %d broken pixels, %d outliers" % (brokenPixCnt, outlierPixCnt))
        # TODO INCOMPLETE

    def _I2CWriteWord(self, writeAddress, data):
        cmd = bytearray(4)
        cmd[0] = writeAddress >> 8
        cmd[1] = writeAddress & 0x00FF
        cmd[2] = data >> 8
        cmd[3] = data & 0x00FF
        dataCheck = [0]

        with self.i2c_device as i2c:
            i2c.write(cmd)
        # print("Wrote:", [hex(i) for i in cmd])
        time.sleep(0.001)
        self._I2CReadWords(writeAddress, dataCheck)
        # print("dataCheck: 0x%x" % dataCheck[0])
        # if (dataCheck != data):
        #    return -2

    _inbuf = bytearray(2 * I2C_READ_LEN)

    def _I2CReadWords(self, addr, buffer, *, end=None):
        # stamp = time.monotonic()
        if end is None:
            remainingWords = len(buffer)
        else:
            remainingWords = end
        offset = 0
        addrbuf = bytearray(2)
        # inbuf = bytearray(2 * I2C_READ_LEN)
        inbuf = self._inbuf

        with self.i2c_device as i2c:
            while remainingWords:
                addrbuf[0] = addr >> 8  # MSB
                addrbuf[1] = addr & 0xFF  # LSB
                read_words = min(remainingWords, I2C_READ_LEN)
                i2c.write_then_readinto(
                    addrbuf, inbuf, in_end=read_words * 2
                )  # in bytes
                # print("-> ", [hex(i) for i in addrbuf])

                __memory_manage()

                outwords = struct.unpack(
                    ">" + "H" * read_words, inbuf[0 : read_words * 2]
                )
                # print("<- (", read_words, ")", [hex(i) for i in outwords])
                for i, w in enumerate(outwords):
                    buffer[offset + i] = w
                offset += read_words
                remainingWords -= read_words
                addr += read_words

#def to_firebase(data):
#   data = list(map(lambda temp: str(temp), data))
#  data=f'{{"json":"{json.dumps(data)}"}}'
  # print(f"Sending data: {data}")
#  print(f"Sending Data <removed for efficiency>")
#  return requests.put(firebase_url_endpoint, data=data)

def __memory_manage(dump=False):
    gc.collect()
    # _mem_free = gc.mem_free()
    # try:
    #     t = bytearray(9160)
    # except MemoryError:
    #     print(f"Memory free: {_mem_free}; BUT, printing memory dump (fragmentation)")
    #     if dump is None: dump = True # If default, then print when memory full
    # if dump:
    #   print("Printing memory dump:")
    #   micropython.mem_info(1)
    #   print("----------------------------------------------")
    #   input("Press enter to continue ...")
    # else:
    #   print(f"Memory free: {_mem_free}")

def main():
  print("Beginning main ...")
  #w = wifi()
  #w.getGoodWIFI()
  #w.printStatus()
  # gc.threshold(gc.mem_free() // 8 + gc.mem_alloc()) # Seriously push the memory managing to the limit! Manages every <n> bytes allocated
  gc.threshold(5000) # Seriously push the memory managing to the limit! Manages every <n> bytes allocated

  __memory_manage()

  ixc = I2C(pins=(18, 17), frequency=800000)
  mlx = MLX90640(ixc)
  mlx.refresh_rate = RefreshRate.REFRESH_2_HZ
  frame = [0]*768

  sleeptime = 2
  num_photo = 60

  for inx in range(num_photo):
    file_name = f"data-{inx}.raw"

  #while True:
      # SCL=6, SDA=5 on QT PY C3
    try:
      print("Querying camera ...\n")
      mlx.getFrame(frame, inx)
      # print(f"Frame received! {frame}")
      print(f"Frame received!")
      print(frame[:10])

      float_array = array.array('d', frame)

      # Scrivi i dati binari nel file
      with open(file_name, 'wb') as file:
        file.write(float_array)
      #to_firebase(frame)

      __memory_manage()


    except Exception as e:
      print(e)
      time.sleep(1.0)

    time.sleep(sleeptime)
#print('raising ...')
#print(f"Self._i2c: {self._i2c=}")
#raise e

if __name__ == '__main__':
  main()
