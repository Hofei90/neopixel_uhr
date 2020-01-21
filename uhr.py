#!/usr/bin/python3

import datetime
import os
import shlex
import subprocess
import threading
import time
from copy import deepcopy

import gpiozero
import toml
import neopixel
import board

import setup_logging


SKRIPTPFAD = os.path.abspath(os.path.dirname(__file__))


def load_config(pfad=SKRIPTPFAD):
    configfile = os.path.join(pfad, "uhr_cfg.toml")
    with open(configfile) as conffile:
        config = toml.loads(conffile.read())
    return config


CONFIG = load_config()
LOGGER = setup_logging.create_logger("uhr", CONFIG["loglevel"])
# LED strip configuration
LED_COUNT = 60  # Number of LED pixels.
LED_PIN = board.D18  # GPIO pin connected to the pixels (must support PWM!).
LED_PIXEL_ORDER = neopixel.GRB  # Strip type and colour ordering

# Zahl stellt den Wert in Minuten dar, wie lange kein Gerät erreichbar sein darf dass die Uhr "abgeschalten" wird
ABSCHALTWERT = 5


class Uhr:
    def __init__(self, pixels, mode):
        self.helligkeit = pixels.brightness
        self.pixels = pixels
        self.helligkeit_geaendert = None
        self.mode_geaendert = None
        self.mode = mode
        self._rgb_leer = None
        self._rgb_sekunde = None
        self._rgb_minute = None
        self._rgb_stunde = None
        self.led_gesetzt = 0
        self.durchlauf_pause = datetime.timedelta(seconds=0)
        self.sleep_time = 0

    def mode_wechseln(self):
        mode = int(self.mode)
        mode_anzahl = len(CONFIG["mode"]) - 1
        if mode_anzahl < 0:
            mode_anzahl = 0

        mode += 1
        if mode > mode_anzahl:
            mode = 0
        self.mode = str(mode)
        now = datetime.datetime.now()
        self.mode_geaendert = now
        alle_led(0, 0, 0, self.pixels)
        self.mode_control(now)
        LOGGER.info(f"Mode geändert auf: {self.mode} um {self.mode_geaendert}Uhr")

    def set_helligkeit(self, helligkeit):
        self.helligkeit = helligkeit
        self.pixels.brightness = self.helligkeit
        self.helligkeit_geaendert = datetime.datetime.now()
        LOGGER.info(f"Helligkeit geändert auf: {self.helligkeit} um {self.helligkeit_geaendert}Uhr")

    def helligkeit_erhoehen(self):
        self.helligkeit += 0.05
        if self.helligkeit > 1:
            self.helligkeit = 0
        self.set_helligkeit(self.helligkeit)

    def helligkeit_verringern(self):
        self.helligkeit -= 0.05
        if self.helligkeit < 0:
            self.helligkeit = 1
        self.set_helligkeit(self.helligkeit)

    def rgb_farben_lesen(self):
        config = deepcopy(CONFIG)
        self._rgb_leer = config["mode"][self.mode]["leer"]
        self._rgb_sekunde = config["mode"][self.mode]["sekunde"]
        self._rgb_minute = config["mode"][self.mode]["minute"]
        self._rgb_stunde = config["mode"][self.mode]["stunde"]

        rgbconf = {"rgb_leer": self._rgb_leer, "rgb_s": self._rgb_sekunde, "rgb_min": self._rgb_minute,
                   "rgb_std": self._rgb_stunde}
        return rgbconf

    def mode_control(self, zeit):
        rgbconf = self.rgb_farben_lesen()
        mode = int(self.mode)
        if mode == 0:
            stdliste = stunden_led_mapping_variante_0()
            stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, rgbdict, \
                self.led_gesetzt = stunde_minute_sekunde_einfach_modus(zeit, stdliste, rgbconf, self.led_gesetzt)
            self.durchlauf_pause = datetime.timedelta(seconds=1)
            self.sleep_time = 0.2
        elif mode == 1:
            stdliste = stunden_led_mapping_variante_0()
            stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, \
                rgbdict = stunde_minute_dauerhaft_modus(zeit, stdliste, rgbconf)
            self.durchlauf_pause = datetime.timedelta(seconds=1)
            self.sleep_time = 0.5
        elif mode == 2:
            stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, \
                rgbdict = uhr_aus_modus(rgbconf)
            self.durchlauf_pause = datetime.timedelta(minutes=1)
            self.sleep_time = 2
        else:
            stunden_leds = [0]
            minuten_leds = [0]
            sekunden_leds = [0]
            sonstige_leds = [0]
            leer_leds = [0]
            rgbdict = self.rgb_farben_lesen()
        LOGGER.debug(f"stunden_leds: {stunden_leds}\n"
                     f"minuten_leds: {minuten_leds}\n"
                     f"sekunden_leds: {sekunden_leds}\n"
                     f"leer_leds: {leer_leds}\n"
                     f"sonstige_leds: {sonstige_leds}\n"
                     f"rgbdict: {rgbdict}")
        led_setzen(stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, rgbdict, self.pixels)


# GPIO
I_MODE_TASTER = gpiozero.Button(3)
I_PLUS_TASTER = gpiozero.Button(4)
I_MINUS_TASTER = gpiozero.Button(17)


def config_schreiben(pfad=SKRIPTPFAD):
    configfile = os.path.join(pfad, "uhr_cfg.toml")
    with open(configfile, "w") as conffile:
        conffile.write(toml.dumps(CONFIG))
    LOGGER.info(f"Schreibe Config: {CONFIG}")


def alle_led(r, g, b, pixels):
    pixels.fill((r, g, b))
    pixels.show()


def stunden_led_mapping_variante_0():
    std0 = [0, 1, 59]
    std1 = [4, 5, 6]
    std2 = [9, 10, 11]
    std3 = [14, 15, 16]
    std4 = [19, 20, 21]
    std5 = [24, 25, 26]
    std6 = [29, 30, 31]
    std7 = [34, 35, 36]
    std8 = [39, 40, 41]
    std9 = [44, 45, 46]
    std10 = [49, 50, 51]
    std11 = [54, 55, 56]
    stdliste = [std0, std1, std2, std3, std4, std5, std6, std7, std8, std9, std10, std11]
    return stdliste


def stunden_index_mapping_ermitteln(zeit):
    if zeit.hour > 11:
        index = zeit.hour - 12
    else:
        index = zeit.hour
    return index


def stunde_minute_sekunde_einfach_modus(zeit, stdliste, rgbdict, led_gesetzt):
    index = stunden_index_mapping_ermitteln(zeit)
    stunden_leds = list(stdliste[index])
    minuten_leds = [zeit.minute]
    sekunden_leds = [zeit.second]
    sonstige_leds = []

    # Schnittfarben berechnen falls "Zeiger" übereinander liegen
    # Stunde mit Minute vergleichen

    if bool(set(stunden_leds) & set(minuten_leds)):
        for counter in range(0, 3):
            rgbdict["rgb_min"][counter] = int((rgbdict["rgb_std"][counter] + rgbdict["rgb_min"][counter]) / 2)
    # Stunde mit Sekunde vergleichen
    if set(stunden_leds) & set(sekunden_leds):
        for counter in range(0, 3):
            rgbdict["rgb_s"][counter] = int((rgbdict["rgb_std"][counter] + rgbdict["rgb_s"][counter]) / 2)
    # Minute mit Sekunde vergleichen
    if set(minuten_leds) & set(sekunden_leds):
        for counter in range(0, 3):
            rgbdict["rgb_s"][counter] = int((rgbdict["rgb_min"][counter] + rgbdict["rgb_s"][counter]) / 2)

    # Neue Leere LED berechnen
    led_gesetzt_neu = set(stunden_leds) | set(minuten_leds) | set(sekunden_leds)
    if isinstance(led_gesetzt, (int, float)):
        led_gesetzt = [led_gesetzt]
    leer_leds = set(led_gesetzt) - set(led_gesetzt_neu)
    return stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, rgbdict, led_gesetzt_neu


def stunde_minute_dauerhaft_modus(zeit, stdliste, rgbdict):
    sekunden_leds = []

    index = stunden_index_mapping_ermitteln(zeit)
    stunden_leds = list(stdliste[index])

    minuten_leds = [minute for minute in range(0, zeit.minute + 1)]

    if zeit.minute == 0:
        leer_leds = list(set(range(0, 60)) - set(stunden_leds) - set(minuten_leds))
    else:
        leer_leds = []

    if max(minuten_leds) < max(stunden_leds):
        if index == 0:
            if zeit.minute <= 1:
                sonstige_leds = [minute for minute in range(0, zeit.minute + 1)]
            elif zeit.minute == 59:
                sontige_leds = [59]
            else:
                sonstige_leds = []
        else:
            sonstige_leds = list(set(stunden_leds) & set(minuten_leds))
            minuten_leds = list(set(minuten_leds) - set(sonstige_leds))
    else:
        sonstige_leds = []

    minuten_leds = list(set(minuten_leds) - set(stunden_leds))
    stunden_leds = list(set(stunden_leds) - set(sonstige_leds))
    sonstige_leds = [(led, (0, 0, 255)) for led in sonstige_leds]

    return stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, rgbdict


def uhr_aus_modus(rgbdict):
    sekunden_leds = []
    minuten_leds = []
    stunden_leds = []
    sonstige_leds = []
    leer_leds = [led for led in range(0, 60)]

    return stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, rgbdict


def led_setzen(stunden_leds, minuten_leds, sekunden_leds, leer_leds, sonstige_leds, rgbdict, pixels):
    # Stunden setzen
    for stunde_led in stunden_leds:
        pixels[stunde_led] = rgbdict["rgb_std"][0], rgbdict["rgb_std"][1], rgbdict["rgb_std"][2]

    # Minute setzen
    for minute_led in minuten_leds:
        pixels[minute_led] = rgbdict["rgb_min"][0], rgbdict["rgb_min"][1], rgbdict["rgb_min"][2]

    # Sekunde setzen
    for sekunde_led in sekunden_leds:
        pixels[sekunde_led] = rgbdict["rgb_s"][0], rgbdict["rgb_s"][1], rgbdict["rgb_s"][2]

    # Leer setzen
    for leer_led in leer_leds:
        pixels[leer_led] = rgbdict["rgb_leer"][0], rgbdict["rgb_leer"][1], rgbdict["rgb_leer"][2]

    # Sonstige LEDs verarbeiten
    # Aufbau -> [index_lednummer, (R, G, B)]
    for led, rgb in sonstige_leds:
        pixels[led] = rgb[0], rgb[1], rgb[2]
    pixels.show()


def shutdown():
    cmd = "sudo shutdown now"
    cmd = shlex.split(cmd)
    subprocess.call(cmd)


# Threads
def check_anwesenheit(uhr, pixels):
    """Funktion, welche als eigener Thread laeuft, um selbststaendig in einem gewissenen Intervall
    alle Geraete in der Toml Liste zu pingen
    arg: Objekt des neopixel LED Ringes
    toml File: status "anwesend", ist kein Geraet von "anwesend" oder "dimmen" erreichbar, LED Helligkeit auf 0
    sobald eine Adresse von status "dimmen" erreichbar ist, wird die Helligkeit verringert"""

    def ping_ping(ip):
        """pingt die IP 2x an
        return (0 | !0) 0 wenn erreichbar"""
        befehl = "ping -c2 -W1 {}".format(ip)
        LOGGER.debug(f"Pinge: {befehl}")
        cmd = shlex.split(befehl)
        return subprocess.call(cmd)

    def ping_bt(bt):
        """pingt die IP 2x an
        return (0 | !0) 0 wenn erreichbar"""
        befehl = "sudo /usr/bin/l2ping -c1 -t1 {}".format(bt)
        LOGGER.debug(f"Pinge: {befehl}")
        cmd = shlex.split(befehl)
        return subprocess.call(cmd)

    def ping_arping(ip, interface):
        """pingt die IP 3x an
               return (0 | !0) 0 wenn erreichbar
        """
        befehl = "/usr/bin/arping -q -c 3 -w 10 -b -f -I {interface} {ip}".format(interface=interface, ip=ip)
        LOGGER.debug(f"Pinge: {befehl}")
        cmd = shlex.split(befehl)
        return subprocess.call(cmd)

    wlanliste = CONFIG["ping"]
    interface = CONFIG["interface"]
    status_anwesend_liste = []
    delta = datetime.timedelta(seconds=301)
    last = datetime.datetime.now()
    status = {}
    while True:
        helligkeit = uhr.helligkeit
        now = datetime.datetime.now()
        # Status der Geräte ermitteln
        if delta.seconds > 300:
            for key_status in wlanliste.keys():
                for key_funkart in wlanliste[key_status].keys():
                    for ip in wlanliste[key_status][key_funkart]:
                        if key_funkart == "ping":
                            status_return = ping_ping(ip)
                        elif key_funkart == "bt":
                            status_return = ping_bt(ip)
                        elif key_funkart == "arping":
                            status_return = ping_arping(ip, interface)
                        else:
                            status_return = False
                        if not status_return:
                            status[key_status] = True
                            break
                        else:
                            status[key_status] = False
            if status["anwesend"]:
                status_anwesend_liste = []  # Geraet von anwesend erreichbar
                helligkeit = uhr.helligkeit
            elif not status["anwesend"] and not status["dimmen"]:  # Wenn kein Geraet erreichbar ist
                if len(status_anwesend_liste) < ABSCHALTWERT + 1:
                    status_anwesend_liste.append(status["anwesend"])
                LOGGER.info(f"Nichts los daheim die {len(status_anwesend_liste)}.")
                if len(status_anwesend_liste) > ABSCHALTWERT:
                    LOGGER.info("Uhr aus, keiner zu Hause")
                    helligkeit = 0
            if status["dimmen"]:
                LOGGER.info("Uhr dimmen, entsprechendes Gerät aktiv")
                helligkeit = 0.03
            if now.hour < 5 and not status["dimmen"]:
                helligkeit = 0
            pixels.brightness = helligkeit
            last = datetime.datetime.now()
        delta = now - last
        time.sleep(60)


def main():
    letzter_durchlauf = datetime.datetime(1970, 1, 1)

    pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=CONFIG["led_helligkeit"],
                               auto_write=False, pixel_order=LED_PIXEL_ORDER)
    uhr = Uhr(pixels, CONFIG["mode_nummer"])
    thread_check_wlan = threading.Thread(target=check_anwesenheit, args=(uhr, pixels))
    thread_check_wlan.start()

    rgbconf = uhr.rgb_farben_lesen()
    alle_led(rgbconf["rgb_leer"][0], rgbconf["rgb_leer"][1], rgbconf["rgb_leer"][2], pixels)

    I_PLUS_TASTER.when_pressed = uhr.helligkeit_erhoehen
    I_MINUS_TASTER.when_pressed = uhr.helligkeit_verringern
    I_MODE_TASTER.when_pressed = uhr.mode_wechseln

    try:
        while True:
            now = datetime.datetime.now()
            if (now - letzter_durchlauf) > uhr.durchlauf_pause:
                uhr.mode_control(now)
                letzter_durchlauf = now
            if uhr.helligkeit_geaendert is not None:
                if (datetime.datetime.now() - uhr.helligkeit_geaendert) > datetime.timedelta(seconds=30):
                    CONFIG["led_helligkeit"] = uhr.helligkeit
                    config_schreiben()
                    uhr.helligkeit_geaendert = None
            if uhr.mode_geaendert is not None:
                if (datetime.datetime.now() - uhr.mode_geaendert) > datetime.timedelta(seconds=30):
                    CONFIG["mode_nummer"] = uhr.mode
                    config_schreiben()
                    uhr.mode_geaendert = None
            time.sleep(uhr.sleep_time)
    finally:
        pixels.brightness = 0
        alle_led(0, 0, 0, pixels)


if __name__ == "__main__":
    main()
