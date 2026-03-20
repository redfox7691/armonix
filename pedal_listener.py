"""Listener per il pedalino piano USB collegato via seriale (es. /dev/ttyACM0).

Il dispositivo invia righe CSV nel formato:  right,center,left
  right  : 0-127  (pedale destro / sustain, valore continuo)
  center : 0 o 1  (pedale centrale / sostenuto, binario)
  left   : 0 o 1  (pedale sinistro / una corda, binario)
"""

import logging
import threading

logger = logging.getLogger(__name__)


class PedalListener(threading.Thread):
    """Legge la porta seriale e chiama callback(right, center, left)."""

    def __init__(self, device_path, baud_rate, callback, stop_event, verbose=False):
        super().__init__(daemon=True, name="pedal-listener")
        self.device_path = device_path
        self.baud_rate = baud_rate
        self.callback = callback
        self.stop_event = stop_event
        self.verbose = verbose
        self._last = {"right": None, "center": None, "left": None}

    def run(self):
        try:
            import serial
        except ImportError:
            logger.error(
                "Modulo 'serial' non trovato: installare python3-serial per il supporto pedali"
            )
            return

        while not self.stop_event.is_set():
            try:
                with serial.Serial(self.device_path, self.baud_rate, timeout=1) as ser:
                    if self.verbose:
                        logger.debug(
                            "Pedali: connesso a %s a %d baud", self.device_path, self.baud_rate
                        )
                    while not self.stop_event.is_set():
                        raw = ser.readline()
                        if not raw:
                            continue
                        self._process(raw.decode("ascii", errors="ignore").strip())
            except Exception as exc:
                if not self.stop_event.is_set():
                    logger.warning("Pedali: errore seriale (%s), riprovo...", exc)
                    self.stop_event.wait(2.0)

    def _process(self, line):
        if not line:
            return
        try:
            parts = line.split(",")
            if len(parts) != 3:
                return
            values = {
                "right":  max(0, min(127, int(parts[0].strip()))),
                "center": 127 if int(parts[1].strip()) else 0,
                "left":   127 if int(parts[2].strip()) else 0,
            }
            for key, val in values.items():
                if val != self._last[key]:
                    self._last[key] = val
                    if self.verbose:
                        logger.debug("Pedale %s: %d", key, val)
                    self.callback(key, val)
        except (ValueError, IndexError):
            pass  # ignora righe malformate
