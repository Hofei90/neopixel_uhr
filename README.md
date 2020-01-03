# Hofei's Neopixel Uhr

## Beschreibung

Die Software steuert einen Neopixel Ring mit 60 LEDs an, zur Darstellung der Uhrzeit.

Mit Hilfe von 2 Tastern lässt sich die Helligkeit variabel einstellen und mit dem 3. Taster zwischen verschiedenen 
Darstellungsmodien wechseln. Die zuletzt ausgewählten Einstellungen werden in einer Config File abgespeichert um bei 
erneuten Start des Programmes die Einstellungen wieder herstellen zu können.

## Installation

Für die Installation, als auch die Ausführung des Skriptes erfordert root-Rechte.

Software installieren:

```console
apt install iputils-arping python3-systemd
```
    
Pythonmodule installieren:

```console
sudo pip3 install requirements.txt
```

Projekt clonen: (die weitere Anleitung als auch die Service Unit geht davon aus, dass das Projekt unter `/home/pi/uhr` installiert wurde. Sollte es zu Abweichungen kommen muss der Pfad in der Service Unit korrigiert werden)

```console
git clone https://github.com/Hofei90/neopixel_uhr.git /home/pi/uhr
```

Anschließend die im Projektordner befindliche Datei `uhr.service` nach `/etc/systemd/system/` kopieren und Rechte 
anpassen.

```console
cp /home/pi/uhr/uhr.service /etc/systemd/system/
chown root:root /etc/systemd/system/uhr.service
chmod 644 /etc/systemd/system/uhr.service
```

Zuletzt die Vorlagenkonfiguration kopieren/umbennen und den Inhalt entsprechend anpassen:

```console
cp /home/pi/uhr/uhr_cfg_vorlage.toml /home/pi/uhr/uhr_cfg.toml
nano /home/pi/uhr/uhr_cfg.toml
```

Mit `systemctl start uhr.service` kann das Programm gestartet werden.

Für den Autostart `systemctl enable uhr.service` ausführen.

Sollte es zu Problemen kommen ist der Aufruf von `journalctl -u uhr.service` und `systemctl status uhr.service` 
hilfreich.

## Verfügbare Anzeige Modien

Aktuell stehen 3 verschiedene Modien zur Verfügung welche mit Hilfe des Modustasters durchgewechselt werden können.

### Modus 0

Anzeige des Stundenzeigers mit 3 LED und Minuten und Sekundenzeiger mit einer LED. Die restlichen LEDs werden immer mit 
der angegebenen Leer Farbe angezeigt.
Gibt es Überschneidungen der LEDs so werden die Farben gemischt.

### Modus 1

Anzeige des Stundenzeigers mit 3 LED und Minuten werden fortlaufend aufgefüllt. Die vergangenen Minutenleds werden nicht 
auf die Leerfarbe zurückgesetzt. So ergibt sich ein sich auffüllender Kreis.
Gibt es Überschneidungen von Minuten und Stunden, wenn die Minutenled noch nicht größer als die Stundenled ist, so wird
eine separte Farbe angezeigt. Sind die Minuten höher als die Stunden, so wird die Stunden in ihrer konfigurierten 
Farbe angezeigt.

### Modus 2

Keine Anzeige von LEDs

## Sonstiges

Die Anzeige schaltet sich nach 0 Uhr bis 5 Uhr aus, wenn kein Gerät läuft welches Dimmen erforderlich macht. Hier wird
davon ausgegangen, dass der Benutzer schläft und keine Anzeige erforderlich ist.
