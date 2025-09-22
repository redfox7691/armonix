import logging
import mido
import os
import threading
import time
import importlib

try:
    from PyQt5 import QtCore  # type: ignore
    QT_AVAILABLE = True
except ImportError:  # pragma: no cover - PyQt5 is optional
    QtCore = None
    QT_AVAILABLE = False

class StateManager(QtCore.QObject if QT_AVAILABLE else object):
    def __init__(
        self,
        verbose=False,
        master="fantom",
        disable_realtime_display=False,
        master_port_keyword=None,
        ketron_port_keyword="MIDI Gadget",
        ble_port_keyword="Bluetooth",
        keypad_device="/dev/input/by-id/usb-1189_USB_Composite_Device_CD70134330363235-if01-event-kbd",
        enable_midi_io=True,
        logger=None,
    ):
        super().__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.verbose = verbose
        self.master = master
        self.disable_realtime_display = disable_realtime_display
        self.master_module = importlib.import_module(f"{master}_midi_filter")
        if master_port_keyword:
            setattr(self.master_module, "MASTER_PORT_KEYWORD", master_port_keyword)
        self.master_port_keyword = getattr(
            self.master_module, "MASTER_PORT_KEYWORD", ""
        )
        self.ketron_port_keyword = ketron_port_keyword or "MIDI Gadget"
        self.ble_port_keyword = ble_port_keyword or "Bluetooth"
        self.midi_io_enabled = enable_midi_io
        self.ledbar = None
        self.master_port = None
        self.ketron_port = None
        self.ble_port = None
        self.state = "waiting"   # 'waiting', 'ready', 'paused'
        if QT_AVAILABLE and QtCore.QCoreApplication.instance() is not None:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.poll_ports)
            self.timer.start(1000)  # Ogni secondo
        else:
            self.timer = None
            self._polling_thread = threading.Thread(
                target=self._polling_loop, daemon=True
            )
            self._polling_thread.start()
        self.led_states = ['yellow'] * 5  # All'inizio: animazione "cavalcante"
        self.anim_counter = 0

        # Tastierino USB (LED K)
        self.keypad_connected = False
        self.keypad_device = (
            keypad_device
            or "/dev/input/by-id/usb-1189_USB_Composite_Device_CD70134330363235-if01-event-kbd"
        )
        self.keypad_listener = None
        self.keypad_stop_event = threading.Event()

        # Bluetooth MIDI (LED B)
        self.ble_connected = False
        self.ble_listener_thread = None
        self.ble_listener_stop = None


    def set_ledbar(self, ledbar):
        self.ledbar = ledbar
        if self.ledbar:
            self.ledbar.set_animating(self.state == "waiting")

    def _polling_loop(self):
        while True:
            self.poll_ports()
            time.sleep(1)

    def poll_ports(self):
        master_port = self.find_port(self.master_port_keyword)
        ketron_port = self.find_port(self.ketron_port_keyword)
        ble_port = self.find_port(self.ble_port_keyword)

        # Aggiorna variabili di stato MIDI principali
        if (master_port != self.master_port) or (ketron_port != self.ketron_port):
            if self.verbose:
                self.logger.debug(
                    "Stato MIDI cambiato: Master=%s, Ketron=%s",
                    "TROVATA" if master_port else "NO",
                    "TROVATA" if ketron_port else "NO",
                )
            self.master_port = master_port
            self.ketron_port = ketron_port

        # Tastierino USB detection + listener
        keypad_present = os.path.exists(self.keypad_device)
        if keypad_present and not self.keypad_connected:
            self.keypad_connected = True
            if self.verbose:
                self.logger.debug("Tastierino USB collegato")
            if self.midi_io_enabled:
                self.start_keypad_listener()
        elif not keypad_present and self.keypad_connected:
            self.keypad_connected = False
            if self.verbose:
                self.logger.debug("Tastierino USB scollegato")
            self.stop_keypad_listener()

        # Bluetooth MIDI detection + listener
        if ble_port and not self.ble_connected:
            self.ble_port = ble_port
            self.ble_connected = True
            if self.verbose:
                self.logger.debug("Dispositivo Bluetooth MIDI trovato: %s", ble_port)
            if self.midi_io_enabled:
                self.start_ble_listener()
        elif not ble_port and self.ble_connected:
            if self.verbose:
                self.logger.debug("Bluetooth MIDI scollegato")
            self.ble_connected = False
            self.ble_port = None
            self.stop_ble_listener()

        # Hook for master-specific port polling
        if hasattr(self.master_module, "poll_ports"):
            self.master_module.poll_ports(self)

        # Aggiorna stato dei LED
        if self.master_port and self.ketron_port:
            if self.state == "waiting":
                if self.verbose:
                    self.logger.debug("Entrambe le porte MIDI trovate, sistema pronto!")
                self.logger.info("Sistema pronto: porte master e Ketron rilevate")
                self.state = "ready"
                if self.ledbar:
                    self.ledbar.set_animating(False)
            if self.state == "ready":
                self.start_master_listener()
                self.led_states = [True, True, self.keypad_connected, self.ble_connected, True]
            elif self.state == "paused":
                self.stop_master_listener()
                self.led_states = [True, True, self.keypad_connected, self.ble_connected, "red"]
        else:
            if self.state != "waiting":
                self.stop_master_listener()
                if self.verbose:
                    self.logger.debug("Una delle porte MIDI è scollegata: torno in attesa.")
                self.logger.info("Una delle porte MIDI è scollegata: ritorno in attesa")
                self.state = "waiting"
                if self.ledbar:
                    self.ledbar.set_animating(True)
            yellow_leds = [False] * 5
            yellow_leds[self.anim_counter % 5] = "yellow"
            self.led_states = yellow_leds
            self.anim_counter += 1

        if self.ledbar:
            self.ledbar.update()

    def find_port(self, keyword):
        if not keyword:
            return None
        for port_name in mido.get_input_names():
            if keyword in port_name:
                return port_name
        return None

    def find_output_port(self, keyword):
        if not keyword:
            return None
        for port_name in mido.get_output_names():
            if keyword in port_name:
                return port_name
        return None

    def get_led_states(self):
        return self.led_states

    def system_pause_on(self):
        if self.verbose:
            self.logger.debug("Sistema in pausa.")
        self.state = "paused"
        self.led_states[4] = "red"
        if self.ledbar:
            self.ledbar.update()

    def system_pause_off(self):
        if self.verbose:
            self.logger.debug("Sistema attivo.")
        self.state = "ready"
        self.led_states[4] = True
        if self.ledbar:
            self.ledbar.update()

    def toggle_enabled(self):
        if self.state == "ready":
            self.state = "paused"
            if self.verbose:
                self.logger.debug("Sistema in pausa: i messaggi MIDI sono ora bloccati.")
            self.led_states[4] = "red"
            if self.ledbar:
                self.ledbar.update()
        elif self.state == "paused":
            self.state = "ready"
            if self.verbose:
                self.logger.debug("Sistema riattivato: i messaggi MIDI vengono inoltrati.")
            self.led_states[4] = True
            if self.ledbar:
                self.ledbar.update()

    # -------- Tastierino USB methods --------
    def on_keypad_event(self, scancode, keycode, is_down):
        if not self.midi_io_enabled:
            return
        if not self.ketron_port:
            if self.verbose:
                self.logger.debug("Ricevuto evento da tastierino ma Ketron non collegato.")
            return
        # Qui richiama la tua callback
        from keypad_midi_callback import keypad_midi_callback
        with mido.open_output(self.ketron_port, exclusive=False) as outport:
            keypad_midi_callback(keycode, is_down, outport, verbose=self.verbose)

    def start_keypad_listener(self):
        if not self.midi_io_enabled:
            return
        if self.keypad_listener and self.keypad_listener.is_alive():
            return  # già attivo
        self.keypad_stop_event.clear()
        def midi_cb(scancode, keycode, is_down):
            self.on_keypad_event(scancode, keycode, is_down)
        from keypadlistener import KeypadListener
        self.keypad_listener = KeypadListener(
            self.keypad_device, midi_cb, self.keypad_stop_event, verbose=self.verbose
        )
        self.keypad_listener.start()
        if self.verbose:
            self.logger.debug("KeypadListener avviato.")

    def stop_keypad_listener(self):
        if self.keypad_listener:
            self.keypad_stop_event.set()
            self.keypad_listener = None
            if self.verbose:
                self.logger.debug("KeypadListener terminato.")

    # -------- Bluetooth MIDI methods --------
    def start_ble_listener(self):
        if not self.midi_io_enabled:
            return
        if self.ble_listener_thread and self.ble_listener_thread.is_alive():
            return  # già attivo
        self.ble_listener_stop = threading.Event()

        def ble_listener():
            import time
            try:
                with mido.open_input(self.ble_port) as port_in, \
                     mido.open_output(self.ketron_port, exclusive=False) as port_out:
                    if self.verbose:
                        self.logger.debug("[BLE] In ascolto sulla porta Bluetooth MIDI.")
                    for msg in port_in:
                        if self.ble_listener_stop.is_set():
                            break
                        port_out.send(msg)
                        if self.verbose:
                            self.logger.debug("[BLE] Ricevuto e inoltrato: %s", msg)
            except Exception as e:
                self.logger.exception("[BLE] Errore: %s", e)

        self.ble_listener_thread = threading.Thread(target=ble_listener, daemon=True)
        self.ble_listener_thread.start()

    def stop_ble_listener(self):
        if self.ble_listener_stop:
            self.ble_listener_stop.set()
        self.ble_listener_thread = None

    # -------- DAW MIDI methods --------
    # -------- Master MIDI methods --------
    def start_master_listener(self):
        if not self.midi_io_enabled:
            return
        if hasattr(self, "master_listener_thread") and self.master_listener_thread and self.master_listener_thread.is_alive():
            return  # già attivo
        self.master_listener_stop = threading.Event()
        filter_func = getattr(self.master_module, "filter_and_translate_msg")

        def master_listener():
            if self.verbose:
                self.logger.debug(
                    "[MASTER-THREAD] Avvio thread, porta Master: %s, porta Ketron: %s",
                    self.master_port,
                    self.ketron_port,
                )
            try:
                with mido.open_input(self.master_port) as inport, mido.open_output(self.ketron_port, exclusive=False) as outport:
                    if self.verbose:
                        self.logger.debug("[MASTER] In ascolto su %s.", self.master)
                    while not self.master_listener_stop.is_set():
                        for msg in inport.iter_pending():
                            try:
                                if self.verbose:
                                    self.logger.debug("[MASTER-DEBUG] Ricevuto: %s", msg)
                                filter_func(
                                    msg,
                                    outport,
                                    self,
                                    armonix_enabled=(self.state == "ready"),
                                    state=self.state,
                                    verbose=self.verbose
                                )
                            except Exception as err:
                                self.logger.exception("[MASTER-FILTER] Errore nel filtro: %s", err)
                        time.sleep(0.001)
            except Exception as e:
                self.logger.exception("[MASTER] Errore: %s", e)

        self.master_listener_thread = threading.Thread(target=master_listener, daemon=True)
        self.master_listener_thread.start()

    def stop_master_listener(self):
        if hasattr(self, "master_listener_stop") and self.master_listener_stop:
            self.master_listener_stop.set()
        thread = getattr(self, "master_listener_thread", None)
        if thread:
            thread.join(timeout=1)
        self.master_listener_thread = None
