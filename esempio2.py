import os
import time
import ujson
import machine
import network
from umqtt.simple import MQTTClient
from ssl import SSLContext
import ssl
from machine import I2C, Pin
from bme import *
import wifi_credentials

def _get_ssl_params(key, cert, _ssl):
    keyfile = key
    certfile = cert
    print(_ssl)
    _ssl.load_cert_chain(certfile, keyfile)
    return _ssl

bme = BME680_I2C(I2C(-1, Pin(44), Pin(43)))


#Enter your AWS IoT endpoint. You can find it in the Settings page of
#your AWS IoT Core console.
#https://docs.aws.amazon.com/iot/latest/developerguide/iot-connect-devices.html
aws_endpoint = b'a2gtmtqc9uqfhn-ats.iot.eu-west-1.amazonaws.com'

#If you followed the blog, these names are already set.
thing_name = "Unimi"
client_id = "Unimi"
private_key = "certs/private.pem.key"
private_cert = "certs/certificate.pem.crt"
_ssl = SSLContext(ssl.PROTOCOL_TLS_CLIENT)


#These are the topics we will subscribe to. We will publish updates to /update.
#We will subscribe to the /update/delta topic to look for changes in the device shadow.
topic_pub = "test_topic"
topic_sub = "test_topic"
_ssl = _get_ssl_params(private_key, private_cert, _ssl)

#Define pins for LED and light sensor. In this example we are using a FeatherS2.
#The sensor and LED are built into the board, and no external connections are required.
light_sensor = machine.ADC(machine.Pin(4))
light_sensor.atten(machine.ADC.ATTN_11DB)
led = machine.Pin(13, machine.Pin.OUT)
info = os.uname()

#Connect to the wireless network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
if not wlan.isconnected():
    print('Connecting to network...')
    wlan.connect(wifi_credentials.ssid, wifi_credentials.password)
    while not wlan.isconnected():
        pass

    print('Connection successful')
    print('Network config:', wlan.ifconfig())



def mqtt_connect(client=client_id, endpoint=aws_endpoint, ssl = _ssl):
    mqtt = MQTTClient(client_id=client, server=endpoint, port=8883, keepalive=1200, ssl=_ssl)
    print("Connecting to AWS IoT...")
    mqtt.connect()
    print("Done")
    return mqtt

def mqtt_publish(client, topic=topic_pub, message=''):
    print("Publishing message...")
    client.publish(topic, message)
    print(message)

def mqtt_subscribe(topic, msg):
    print("Message received...")
    message = ujson.loads(msg)
    print(topic, message)
    if message['state']['led']:
        led_state(message)
    print("Done")

def led_state(message):
    led.value(message['state']['led']['onboard'])

#We use our helper function to connect to AWS IoT Core.
#The callback function mqtt_subscribe is what will be called if we
#get a new message on topic_sub.
try:
    mqtt = mqtt_connect(client_id, aws_endpoint,  _ssl)
    mqtt.set_callback(mqtt_subscribe)
    mqtt.subscribe(topic_sub)
except:
    print("Unable to connect to MQTT.")


while True:
#Check for messages.
    try:
        mqtt.check_msg()
    except:
        print("Unable to check for messages.")

    temp = f"{bme.temperature}"
    hum = f"{bme.humidity}"
    pres = f"{bme.pressure}"
    gas = f"{bme.gas}"

    mesg = ujson.dumps({
        "state":{
            "reported": {
                "device": {
                    "client": client_id,
                    "uptime": time.ticks_ms(),
                    "hardware": info[0],
                    "firmware": info[2]
                },
                "sensors": {
                    "temp": temp,
                    "hum": hum,
                    "pres": pres,
                    "gas": gas
                }
            }
        }
    })

#Using the message above, the device shadow is updated.
    try:
        mqtt_publish(client=mqtt, message=mesg)
    except:
        print("Unable to publish message.")

#Wait for 10 seconds before checking for messages and publishing a new update.
    print("Sleep for 10 seconds")
    time.sleep(10)
