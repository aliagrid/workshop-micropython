from bme import *
from machine import I2C, Pin
import time
bme = BME680_I2C(I2C(-1, Pin(44), Pin(43)))


import machine
led = machine.Pin(2,machine.Pin.OUT)
led.off()

# ************************
# Configure the ESP32 wifi
# as STAtion mode.

import network
import wifi_credentials

sta = network.WLAN(network.STA_IF)
if not sta.isconnected():
    print('connecting to network...')
    sta.active(True)
    #sta.connect('your wifi ssid', 'your wifi password')
    sta.connect(wifi_credentials.ssid, wifi_credentials.password)
    while not sta.isconnected():
        pass
print('network config:', sta.ifconfig())

# ************************
# Configure the socket connection
# over TCP/IP
import socket

# AF_INET - use Internet Protocol v4 addresses
# SOCK_STREAM means that it is a TCP socket.
# SOCK_DGRAM means that it is a UDP socket.
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('',80)) # specifies that the socket is reachable 
#                 by any address the machine happens to have
s.listen(5)     # max of 5 socket connections


bme = BME680_I2C(I2C(-1, Pin(44), Pin(43)))


# ************************
# Function for creating the
# web page to be displayed
def web_page():
    temp = f"{bme.temperature}"
    hum = f"{bme.humidity}"
    pres = f"{bme.pressure}"
    gas = f"{bme.gas}"

    html_page = """   
      <html>   
      <head>   
       <meta content="width=device-width, initial-scale=1" name="viewport"></meta>   
      </head>   
      <body>   
        <center><h2>ESP32 Web Server in MicroPython </h2></center>      
        <center><p>Temperature is now <strong>""" + temp + """</strong>.</p></center>
        <center><p>Humidity is now <strong>""" + hum + """</strong>.</p></center>
        <center><p>Pressure is now <strong>""" + pres + """</strong>.</p></center>
        <center><p>Gas is now <strong>""" + gas + """</strong>.</p></center>   
      </body>   
      </html>"""  
    return html_page   

while True:
    # Socket accept() 
    conn, addr = s.accept()
    print("Got connection from %s" % str(addr))
    
    # Socket receive()
    request=conn.recv(1024)
    print("")
    print("")
    print("Content %s" % str(request))


    response = web_page()
    conn.send('HTTP/1.1 200 OK\n')
    conn.send('Content-Type: text/html\n')
    conn.send('Connection: close\n\n')
    conn.sendall(response)
    
    # Socket close()
    conn.close()

