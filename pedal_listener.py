"""Listener per la pedaliera MIDI (es. Arduino Leonardo MIDI 1).

Il dispositivo invia CC standard:
  CC 64 (sustain)   : 0-127  (pedale destro, valore continuo)
  CC 66 (sostenuto) : 0 o 127  (pedale centrale, binario)
  CC 67 (una corda) : 0 o 127  (pedale sinistro, binario)
"""

import logging
import threading

import mido

logger = logging.getLogger(__name__)

# Mapping CC number → pedal key
CC_TO_PEDAL = {
    64: "right",    # sustain
    66: "center",   # sostenuto
    67: "left",     # soft / una corda
}


class PedalListener(threading.Thread):
    """Ascolta una porta MIDI e chiama callback(pedal_key, value) per CC 64/66/67."""

    def __init__(self, port_name, callback, stop_event, verbose=False):
        super().__init__(daemon=True, name="pedal-listener")
        self.port_name = port_name
        self.callback = callback
        self.stop_event = stop_event
        self.verbose = verbose

    def run(self):
        while not self.stop_event.is_set():
            try:
                with mido.open_input(self.port_name) as port:
                    if self.verbose:
                        logger.debug("Pedali MIDI: connesso a %s", self.port_name)
                    while not self.stop_event.is_set():
                        for msg in port.iter_pending():
                            self._process(msg)
                        self.stop_event.wait(0.005)
            except Exception as exc:
                if not self.stop_event.is_set():
                    logger.warning("Pedali MIDI: errore (%s), riprovo...", exc)
                    self.stop_event.wait(2.0)

    def _process(self, msg):
        if msg.type != "control_change":
            return
        pedal_key = CC_TO_PEDAL.get(msg.control)
        if pedal_key is None:
            return
        if self.verbose:
            logger.debug("Pedale %s: %d", pedal_key, msg.value)
        self.callback(pedal_key, msg.value)
