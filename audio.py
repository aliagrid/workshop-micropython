import os
import machine
from machine import I2S, Pin
from machine import SDCard
from ulab import numpy as np
from ulab import utils as utils
import time

files = 43200
length = 5


sd = SDCard(slot=3, miso=12, mosi=13, sck=14, cs=15)
vfs=os.VfsFat(sd)
os.mount(vfs, "/sd")  # mount

# ======= I2S CONFIGURATION =======
SCK_PIN = 40
WS_PIN = 38
SD_PIN = 39
PIN_I2S_LR = 48
I2S_ID = 0
BUFFER_LENGTH_IN_BYTES = 40000
# ======= I2S CONFIGURATION =======

for i in range(files):

    # ======= AUDIO CONFIGURATION =======
    WAV_FILE = f"mic-{i}.wav"
    RECORD_TIME_IN_SECONDS = length
    WAV_SAMPLE_SIZE_IN_BITS = 16
    FORMAT = I2S.MONO
    SAMPLE_RATE_IN_HZ = 22_050
    # ======= AUDIO CONFIGURATION =======

    format_to_channels = {I2S.MONO: 1, I2S.STEREO: 2}
    NUM_CHANNELS = format_to_channels[FORMAT]
    WAV_SAMPLE_SIZE_IN_BYTES = WAV_SAMPLE_SIZE_IN_BITS // 8
    RECORDING_SIZE_IN_BYTES = (
        RECORD_TIME_IN_SECONDS * SAMPLE_RATE_IN_HZ * WAV_SAMPLE_SIZE_IN_BYTES * NUM_CHANNELS
    )


    def create_wav_header(sampleRate, bitsPerSample, num_channels, num_samples):
        datasize = num_samples * num_channels * bitsPerSample // 8
        o = bytes("RIFF", "ascii")  # (4byte) Marks file as RIFF
        o += (datasize + 36).to_bytes(
            4, "little"
        )  # (4byte) File size in bytes excluding this and RIFF marker
        o += bytes("WAVE", "ascii")  # (4byte) File type
        o += bytes("fmt ", "ascii")  # (4byte) Format Chunk Marker
        o += (16).to_bytes(4, "little")  # (4byte) Length of above format data
        o += (1).to_bytes(2, "little")  # (2byte) Format type (1 - PCM)
        o += (num_channels).to_bytes(2, "little")  # (2byte)
        o += (sampleRate).to_bytes(4, "little")  # (4byte)
        o += (sampleRate * num_channels * bitsPerSample // 8).to_bytes(4, "little")  # (4byte)
        o += (num_channels * bitsPerSample // 8).to_bytes(2, "little")  # (2byte)
        o += (bitsPerSample).to_bytes(2, "little")  # (2byte)
        o += bytes("data", "ascii")  # (4byte) Data Chunk Marker
        o += (datasize).to_bytes(4, "little")  # (4byte) Data size in bytes
        return o


    wav = open("/sd/{}".format(WAV_FILE), "wb")

    # create header for WAV file and write to SD card
    wav_header = create_wav_header(
        SAMPLE_RATE_IN_HZ,
        WAV_SAMPLE_SIZE_IN_BITS,
        NUM_CHANNELS,
        SAMPLE_RATE_IN_HZ * RECORD_TIME_IN_SECONDS,
    )
    num_bytes_written = wav.write(wav_header)
    #num_bytes_written = wav
    print(len(wav_header), "header length")

    lr = Pin(PIN_I2S_LR, Pin.OUT, value=1)


    audio_in = I2S(
        I2S_ID,
        sck=Pin(SCK_PIN),
        ws=Pin(WS_PIN),
        sd=Pin(SD_PIN),
        mode=I2S.RX,
        bits=WAV_SAMPLE_SIZE_IN_BITS,
        format=FORMAT,
        rate=SAMPLE_RATE_IN_HZ,
        ibuf=BUFFER_LENGTH_IN_BYTES,
    )

    # allocate sample arrays
    # memoryview used to reduce heap allocation in while loop
    mic_samples = bytearray(10000)
    mic_samples_mv = memoryview(mic_samples)

    num_sample_bytes_written_to_wav = 0

    print("Recording size: {} bytes".format(RECORDING_SIZE_IN_BYTES))
    print("==========  START RECORDING ==========")
    try:
        while num_sample_bytes_written_to_wav < RECORDING_SIZE_IN_BYTES:
            # read a block of samples from the I2S microphone
            num_bytes_read_from_mic = audio_in.readinto(mic_samples_mv)
            if num_bytes_read_from_mic > 0:
                num_bytes_to_write = min(
                    num_bytes_read_from_mic, RECORDING_SIZE_IN_BYTES - num_sample_bytes_written_to_wav
                )
                # write samples to WAV file
                #I2S.shift(buf=mic_samples_mv, bits=WAV_SAMPLE_SIZE_IN_BITS, shift=1)
                num_bytes_written = wav.write(mic_samples_mv[:num_bytes_to_write])
                num_sample_bytes_written_to_wav += num_bytes_written

        print("==========  DONE RECORDING ==========")
    except (KeyboardInterrupt, Exception) as e:
        print("caught exception {} {}".format(type(e).__name__, e))

    # cleanup
    wav.close()


os.umount("/sd")
sd.deinit()

audio_in.deinit()
