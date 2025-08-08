import mido
import os
import threading
from fantom_midi_filter import filter_and_translate_fantom_msg
from launchkey_midi_filter import filter_and_translate_launchkey_msg
from PyQt5 import QtCore

class StateManager(QtCore.QObject):
    def __init__(self, verbose=False, master="fantom"):
        super().__init__()
        self.verbose = verbose
        self.master = master
        self.ledbar = None
        self.master_port = None
        self.ketron_port = None
        self.ble_port = None
        self.state = "waiting"   # 'waiting', 'ready', 'paused'
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.poll_ports)
        self.timer.start(1000)  # Ogni secondo
        self.led_states = ['yellow'] * 5  # All'inizio: animazione "cavalcante"
        self.anim_counter = 0

        # Tastierino USB (LED K)
        self.keypad_connected = False
        self.keypad_device = "/dev/input/by-id/usb-1189_USB_Composite_Device_CD70134330363235-if01-event-kbd"
        self.keypad_listener = None
        self.keypad_stop_event = threading.Event()

        # Bluetooth MIDI (LED B)
        self.ble_connected = False
        self.ble_listener_thread = None
        self.ble_listener_stop = None

    def set_ledbar(self, ledbar):
        self.ledbar = ledbar
        self.ledbar.set_animating(self.state == "waiting")

    def poll_ports(self):
        if self.master == "fantom":
            master_port = self.find_port("FANTOM-06 07")
        else:
            master_port = self.find_port("Launchkey MK3 88 LKMK3 MIDI In")
        ketron_port = self.find_port("MIDI Gadget")
        ble_port = self.find_port("Bluetooth")

        # Aggiorna variabili di stato MIDI principali
        if (master_port != self.master_port) or (ketron_port != self.ketron_port):
            if self.verbose:
                print(f"Stato MIDI cambiato: Master={'TROVATA' if master_port else 'NO'}, Ketron={'TROVATA' if ketron_port else 'NO'}")
            self.master_port = master_port
            self.ketron_port = ketron_port

        # Tastierino USB detection + listener
        keypad_present = os.path.exists(self.keypad_device)
        if keypad_present and not self.keypad_connected:
            self.keypad_connected = True
            if self.verbose:
                print("Tastierino USB collegato")
            self.start_keypad_listener()
        elif not keypad_present and self.keypad_connected:
            self.keypad_connected = False
            if self.verbose:
                print("Tastierino USB scollegato")
            self.stop_keypad_listener()

        # Bluetooth MIDI detection + listener
        if ble_port and not self.ble_connected:
            self.ble_port = ble_port
            self.ble_connected = True
            if self.verbose:
                print(f"Dispositivo Bluetooth MIDI trovato: {ble_port}")
            self.start_ble_listener()
        elif not ble_port and self.ble_connected:
            if self.verbose:
                print("Bluetooth MIDI scollegato")
            self.ble_connected = False
            self.ble_port = None
            self.stop_ble_listener()

        # Aggiorna stato dei LED
        if self.master_port and self.ketron_port:
            if self.state == "waiting":
                if self.verbose:
                    print("Entrambe le porte MIDI trovate, sistema pronto!")
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
                    print("Una delle porte MIDI è scollegata: torno in attesa.")
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
        for port_name in mido.get_input_names():
            if keyword in port_name:
                return port_name
        return None

    def get_led_states(self):
        return self.led_states

    def system_pause_on(self):
        if self.verbose:
            print("Sistema in pausa.")
        self.state = "paused"
        self.led_states[4] = "red"
        if self.ledbar:
            self.ledbar.update()

    def system_pause_off(self):
        if self.verbose:
            print("Sistema attivo.")
        self.state = "ready"
        self.led_states[4] = True
        if self.ledbar:
            self.ledbar.update()

    def toggle_enabled(self):
        if self.state == "ready":
            self.state = "paused"
            if self.verbose:
                print("Sistema in pausa: i messaggi MIDI sono ora bloccati.")
            self.led_states[4] = "red"
            if self.ledbar:
                self.ledbar.update()
        elif self.state == "paused":
            self.state = "ready"
            if self.verbose:
                print("Sistema riattivato: i messaggi MIDI vengono inoltrati.")
            self.led_states[4] = True
            if self.ledbar:
                self.ledbar.update()

    # -------- Tastierino USB methods --------
    def on_keypad_event(self, scancode, keycode, is_down):
        if not self.ketron_port:
            if self.verbose:
                print("Ricevuto evento da tastierino ma Ketron non collegato.")
            return
        # Qui richiama la tua callback
        from keypad_midi_callback import keypad_midi_callback
        with mido.open_output(self.ketron_port, exclusive=False) as outport:
            keypad_midi_callback(keycode, is_down, outport, verbose=self.verbose)

    def start_keypad_listener(self):
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
            print("KeypadListener avviato.")

    def stop_keypad_listener(self):
        if self.keypad_listener:
            self.keypad_stop_event.set()
            self.keypad_listener = None
            if self.verbose:
                print("KeypadListener terminato.")

    # -------- Bluetooth MIDI methods --------
    def start_ble_listener(self):
        if self.ble_listener_thread and self.ble_listener_thread.is_alive():
            return  # già attivo
        self.ble_listener_stop = threading.Event()

        def ble_listener():
            import time
            try:
                with mido.open_input(self.ble_port) as port_in, \
                     mido.open_output(self.ketron_port, exclusive=False) as port_out:
                    if self.verbose:
                        print("[BLE] In ascolto sulla porta Bluetooth MIDI.")
                    for msg in port_in:
                        if self.ble_listener_stop.is_set():
                            break
                        port_out.send(msg)
                        if self.verbose:
                            print(f"[BLE] Ricevuto e inoltrato: {msg}")
            except Exception as e:
                if self.verbose:
                    print(f"[BLE] Errore: {e}")

        self.ble_listener_thread = threading.Thread(target=ble_listener, daemon=True)
        self.ble_listener_thread.start()

    def stop_ble_listener(self):
        if self.ble_listener_stop:
            self.ble_listener_stop.set()
        self.ble_listener_thread = None

    # -------- Master MIDI methods --------
    def start_master_listener(self):
        if hasattr(self, "master_listener_thread") and self.master_listener_thread and self.master_listener_thread.is_alive():
            return  # già attivo
        self.master_listener_stop = threading.Event()
        filter_func = (
            filter_and_translate_fantom_msg
            if self.master == "fantom"
            else filter_and_translate_launchkey_msg
        )

        def master_listener():
            if self.verbose:
                print(f"[MASTER-THREAD] Avvio thread, porta Master: {self.master_port}, porta Ketron: {self.ketron_port}")
            try:
                with mido.open_input(self.master_port) as inport, mido.open_output(self.ketron_port, exclusive=False) as outport:
                    if self.verbose:
                        print(f"[MASTER] In ascolto su {self.master}.")
                    for msg in inport:
                        if self.master_listener_stop.is_set():
                            break
                        try:
                            if self.verbose:
                                print(f"[MASTER-DEBUG] Ricevuto: {msg}")
                            filter_func(
                                msg,
                                outport,
                                self,
                                armonix_enabled=(self.state == "ready"),
                                state=self.state,
                                verbose=self.verbose
                            )
                        except Exception as err:
                            print(f"[MASTER-FILTER] Errore nel filtro: {err}")
            except Exception as e:
                if self.verbose:
                    print(f"[MASTER] Errore: {e}")

        self.master_listener_thread = threading.Thread(target=master_listener, daemon=True)
        self.master_listener_thread.start()

    def stop_master_listener(self):
        if hasattr(self, "master_listener_stop") and self.master_listener_stop:
            self.master_listener_stop.set()
        self.master_listener_thread = None
