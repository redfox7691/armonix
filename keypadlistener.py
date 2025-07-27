import threading
from evdev import InputDevice, categorize, ecodes

class KeypadListener(threading.Thread):
    def __init__(self, device_path, midi_callback, stop_event=None):
        super().__init__()
        self.device_path = device_path
        self.midi_callback = midi_callback  # Funzione che riceve (scancode, keycode)
        self.stop_event = stop_event or threading.Event()
        self.daemon = True  # Così non blocca lo shutdown del programma

    def run(self):
        try:
            dev = InputDevice(self.device_path)
            for event in dev.read_loop():
                if self.stop_event.is_set():
                    break
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    if key_event.keystate == key_event.key_down:
                        self.midi_callback(key_event.scancode, key_event.keycode)
        except Exception as e:
            print(f"Errore KeypadListener: {e}")
