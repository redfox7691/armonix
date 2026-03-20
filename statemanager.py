import json
import logging
import mido
import os
import re
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
        pianoteq_config=None,
        pedals_config=None,
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

        # Pianoteq
        self.pianoteq_config = pianoteq_config
        self.pianoteq_mode = None   # None | "full" | "split"
        self.pianoteq_port = None   # ALSA output port name for Pianoteq

        # Pedali seriali
        self.pedals_config = pedals_config
        self.pedals_connected = False
        self.pedal_listener = None
        self.pedal_stop_event = threading.Event()
        self._pedal_ketron_out = None       # porte aperte e cachate per i pedali
        self._pedal_ketron_out_name = None
        self._pedal_pianoteq_out = None
        self._pedal_pianoteq_out_name = None
        self._pedal_midi_cfg = self._load_pedal_midi_config()

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

        # Pedali seriali detection + listener
        if self.pedals_config and self.pedals_config.enabled:
            pedals_present = os.path.exists(self.pedals_config.device_path)
            if pedals_present and not self.pedals_connected:
                self.pedals_connected = True
                if self.verbose:
                    self.logger.debug("Pedalino seriale collegato: %s", self.pedals_config.device_path)
                if self.midi_io_enabled:
                    self.start_pedal_listener()
            elif not pedals_present and self.pedals_connected:
                self.pedals_connected = False
                if self.verbose:
                    self.logger.debug("Pedalino seriale scollegato")
                self.stop_pedal_listener()

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
    def set_pianoteq_mode(self, mode):
        """Switch Pianoteq routing mode.

        Possible values: ``"full"``, ``"split"``, or ``None`` (off).
        Calling with the currently active mode toggles it off.
        """
        if mode == self.pianoteq_mode:
            mode = None  # toggle off

        if mode in ("full", "full-solo", "split", "split-solo"):
            if not self.pianoteq_config or not self.pianoteq_config.enabled:
                self.logger.warning("Pianoteq non configurato (executable vuoto)")
                return
            from pianoteq_manager import ensure_pianoteq_running
            if not ensure_pianoteq_running(self.pianoteq_config, self.logger):
                self.logger.error("Pianoteq non disponibile")
                return
            port = self.find_output_port(self.pianoteq_config.port_keyword)
            if not port:
                self.logger.error(
                    "Porta MIDI Pianoteq non trovata (keyword=%s)",
                    self.pianoteq_config.port_keyword,
                )
                return
            self.pianoteq_port = port
        else:
            self.pianoteq_port = None

        self.pianoteq_mode = mode
        self.logger.info("Modalità Pianoteq: %s", mode or "off")
        if hasattr(self.master_module, "update_pianoteq_display"):
            self.master_module.update_pianoteq_display(mode, self.verbose)
        return self.pianoteq_mode

    def load_pianoteq_preset(self, preset_name):
        """Carica un preset Pianoteq via JSON-RPC (solo se una modalità Pianoteq è attiva)."""
        if not self.pianoteq_mode:
            self.logger.warning("load_pianoteq_preset: nessuna modalità Pianoteq attiva")
            return
        url = (
            self.pianoteq_config.jsonrpc_url
            if self.pianoteq_config
            else "http://127.0.0.1:8081/jsonrpc"
        )
        from pianoteq_rpc import load_preset
        ok = load_preset(url, preset_name)
        if ok and hasattr(self.master_module, "show_temp_pianoteq_display"):
            self.master_module.show_temp_pianoteq_display(preset_name, self.verbose)

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
            keypad_midi_callback(keycode, is_down, outport, verbose=self.verbose, state_manager=self)

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

    # -------- Pedali seriali methods --------

    def _load_pedal_midi_config(self):
        """Carica pedals_config.json; ritorna None se non trovato o non valido."""
        from paths import get_config_path
        path = get_config_path("pedals_config.json")
        try:
            with open(path) as f:
                raw = f.read()
            # Rimuovi commenti stile // e # (come nel loader del launchkey)
            raw = re.sub(r"//.*", "", raw)
            raw = re.sub(r"#.*", "", raw)
            return json.loads(raw)
        except Exception as exc:
            self.logger.warning("pedals_config.json non trovato o non valido: %s", exc)
            return None

    def _build_pedal_msgs(self, pedal_key, value, dest):
        """Costruisce la lista di mido.Message o (dest, bytes) SysEx per un pedale.

        pedal_key : "right" | "center" | "left"
        value     : 0-127 (right) oppure 0 o 127 (center/left)
        dest      : "evm" | "pianoteq"
        Restituisce (midi_messages, sysex_list) dove:
          midi_messages = lista di mido.Message
          sysex_list    = lista di liste di byte (senza F0/F7)
        """
        midi_msgs = []
        sysex_list = []

        cfg = (self._pedal_midi_cfg or {}).get(pedal_key, {}).get(dest)
        if cfg is None:
            # Fallback hardcoded
            controls = {"right": 64, "center": 66, "left": 67}
            midi_msgs.append(mido.Message("control_change", channel=0,
                                          control=controls[pedal_key], value=value))
            return midi_msgs, sysex_list

        t = cfg.get("type", "CC")
        if t == "CC":
            midi_msgs.append(mido.Message(
                "control_change",
                channel=cfg.get("channel", 0),
                control=cfg.get("control", 0),
                value=value,
            ))
        elif t == "SYSEX":
            key = "pressed" if value > 0 else "released"
            data = cfg.get(key)
            if data is not None:
                sysex_list.append(data)
        elif t == "SYSEX_VALUE":
            template = cfg.get("template", [])
            sysex_list.append(template + [value])

        return midi_msgs, sysex_list

    def on_pedal_event(self, pedal_key, value):
        """Invia il messaggio del singolo pedale cambiato alle porte attive."""

        def _send_to(port_obj, dest):
            midi_msgs, sysex_list = self._build_pedal_msgs(pedal_key, value, dest)
            for msg in midi_msgs:
                port_obj.send(msg)
            for data in sysex_list:
                port_obj.send(mido.Message("sysex", data=data))

        # Ketron: sempre, eccetto in modalità full-solo
        if self.ketron_port and self.pianoteq_mode != "full-solo":
            if self._pedal_ketron_out_name != self.ketron_port:
                if self._pedal_ketron_out:
                    try:
                        self._pedal_ketron_out.close()
                    except Exception:
                        pass
                try:
                    self._pedal_ketron_out = mido.open_output(self.ketron_port, exclusive=False)
                    self._pedal_ketron_out_name = self.ketron_port
                except Exception as exc:
                    self.logger.error("Pedali: impossibile aprire porta Ketron: %s", exc)
                    self._pedal_ketron_out = None
                    self._pedal_ketron_out_name = None
            if self._pedal_ketron_out:
                _send_to(self._pedal_ketron_out, "evm")

        # Pianoteq: se una modalità è attiva
        if self.pianoteq_port and self.pianoteq_mode:
            if self._pedal_pianoteq_out_name != self.pianoteq_port:
                if self._pedal_pianoteq_out:
                    try:
                        self._pedal_pianoteq_out.close()
                    except Exception:
                        pass
                try:
                    self._pedal_pianoteq_out = mido.open_output(self.pianoteq_port, exclusive=False)
                    self._pedal_pianoteq_out_name = self.pianoteq_port
                except Exception as exc:
                    self.logger.error("Pedali: impossibile aprire porta Pianoteq: %s", exc)
                    self._pedal_pianoteq_out = None
                    self._pedal_pianoteq_out_name = None
            if self._pedal_pianoteq_out:
                _send_to(self._pedal_pianoteq_out, "pianoteq")

    def start_pedal_listener(self):
        if not self.midi_io_enabled:
            return
        if self.pedal_listener and self.pedal_listener.is_alive():
            return
        self.pedal_stop_event.clear()
        from pedal_listener import PedalListener
        self.pedal_listener = PedalListener(
            self.pedals_config.device_path,
            self.pedals_config.baud_rate,
            self.on_pedal_event,
            self.pedal_stop_event,
            verbose=self.verbose,
        )
        self.pedal_listener.start()
        if self.verbose:
            self.logger.debug("PedalListener avviato su %s.", self.pedals_config.device_path)

    def stop_pedal_listener(self):
        if self.pedal_listener:
            self.pedal_stop_event.set()
            self.pedal_listener = None
            if self.verbose:
                self.logger.debug("PedalListener terminato.")

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
            # Capture the stop event locally so that a subsequent
            # start_master_listener() call (which reassigns
            # self.master_listener_stop) cannot accidentally keep this
            # thread alive.
            stop = self.master_listener_stop
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
                    while not stop.is_set():
                        for msg in inport.iter_pending():
                            if stop.is_set():
                                break
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
