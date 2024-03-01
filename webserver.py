
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

# ************************
# Function for creating the
# web page to be displayed
def web_page():
    if led.value()==1:
        led_state = 'ON'
        print('led is ON')
    elif led.value()==0:
        led_state = 'OFF'
        print('led is OFF')

    html_page = """
      <html>
      <head>
       <meta content="width=device-width, initial-scale=1" name="viewport"></meta>
      </head>
      <body>
        <center><h2>ESP32 Web Server in MicroPython </h2></center>
        <center>
         <form>
          <button name="LED" type="submit" value="1"> LED ON </button>
          <button name="LED" type="submit" value="0"> LED OFF </button>
         </form>
        </center>
        <center><p>LED is now <strong>""" + led_state + """</strong>.</p></center>
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

    # Socket send()
    request = str(request)
    led_on = request.find('/?LED=1')
    led_off = request.find('/?LED=0')
    if led_on == 6:
        print('LED ON')
        print(str(led_on))
        led.value(1)
    elif led_off == 6:
        print('LED OFF')
        print(str(led_off))
        led.value(0)
    response = web_page()
    conn.send('HTTP/1.1 200 OK\n')
    conn.send('Content-Type: text/html\n')
    conn.send('Connection: close\n\n')
    conn.sendall(response)

    # Socket close()
    conn.close()
