import machine
import neopixel
import time

# Configura il pin GPIO a cui è collegato il Neopixel
pin_neopixel = machine.Pin(48)  # Sostituisci con il numero del tuo pin GPIO
num_leds = 1  # Numero totale di LED nel tuo Neopixel

# Crea un oggetto Neopixel
np = neopixel.NeoPixel(pin_neopixel, num_leds)

def reset_timer_callback(timer):
    # Questa funzione verrà chiamata quando il timer scade
    print("Reset in corso...")
    machine.reset()

def lampeggio_led():
    # Cambia il colore del Neopixel (rosso, verde, blu)
    np[0] = (255, 0, 0)  # Rosso
    np.write()
    time.sleep(0.5)

    np[0] = (0, 255, 0)  # Verde
    np.write()
    time.sleep(0.5)

    np[0] = (0, 0, 255)  # Blu
    np.write()
    time.sleep(0.5)
# Il tuo codice principale può andare qui

while True:
    # Lampeggia il Neopixel nel ciclo principale
    lampeggio_led()
