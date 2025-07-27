import mido
import os
import threading
from PyQt5 import QtCore
from keypad_midi_callback import keypad_midi_callback  # Assicurati che sia nel PYTHONPATH
from keypadlistener import KeypadListener  # Il thread listener che hai già

class StateManager(QtCore.QObject):
    def __init__(self, verbose=False):
        super().__init__()
        self.verbose = verbose
        self.ledbar = None
        self.fantom_port = None
        self.ketron_port = None
        self.state = "waiting"   # 'waiting', 'ready', 'paused'
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.poll_ports)
        self.timer.start(1000)  # Ogni secondo
        self.led_states = ['yellow'] * 5  # All'inizio: animazione "cavalcante"
        self.anim_counter = 0

        # Tastierino USB (LED K)
        self.keypad_connected = False
        self.keypad_device = "/dev/input/event8"  # Modifica se necessario
        self.keypad_listener = None
        self.keypad_stop_event = threading.Event()

    def set_ledbar(self, ledbar):
        self.ledbar = ledbar
        self.ledbar.set_animating(self.state == "waiting")

    def on_keypad_event(self, scancode, keycode, is_down):
        # Chiamata dal KeypadListener per ogni tasto premuto/rilasciato
        if self.ketron_port:
            keypad_midi_callback(keycode, is_down, self.ketron_port)
        elif self.verbose:
            print(f"Ricevuto evento da tastierino ma Ketron non collegato.")

    def poll_ports(self):
        fantom = self.find_port("FANTOM-06 07")
        ketron = self.find_port("MIDI Gadget")

        # --- Keyboard detection (LED K + listener)
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

        # --- Logica principale per lo stato dei LED
        if fantom and ketron:
            if self.state == "waiting":
                if self.verbose:
                    print("Entrambe le porte MIDI trovate, sistema pronto!")
                self.state = "ready"
                if self.ledbar:
                    self.ledbar.set_animating(False)
                self.led_states = [True, True, self.keypad_connected, False, True]
            elif self.state == "ready":
                self.led_states = [True, True, self.keypad_connected, False, True]
            elif self.state == "paused":
                self.led_states = [True, True, self.keypad_connected, False, "red"]
        else:
            if self.state != "waiting":
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

    def start_keypad_listener(self):
        if self.keypad_listener and self.keypad_listener.is_alive():
            return  # Già attivo
        self.keypad_stop_event.clear()
        # La callback on_keypad_event riceve (scancode, keycode, is_down)
        def midi_cb(scancode, keycode, is_down):
            self.on_keypad_event(scancode, keycode, is_down)
        self.keypad_listener = KeypadListener(
            self.keypad_device, midi_cb, self.keypad_stop_event
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

    def find_port(self, keyword):
        for port_name in mido.get_input_names():
            if keyword in port_name:
                return port_name
        return None

    def get_led_states(self):
        return self.led_states

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
        # Negli altri stati il click non ha effetto