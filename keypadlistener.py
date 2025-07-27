import threading
from evdev import InputDevice, categorize, ecodes

class KeypadListener(threading.Thread):
    def __init__(self, device_path, midi_callback, stop_event):
        super().__init__()
        self.device_path = device_path
        self.midi_callback = midi_callback
        self.stop_event = stop_event

    def run(self):
        try:
            dev = InputDevice(self.device_path)
            print(f"[KeypadListener] In ascolto su {self.device_path}")
            for event in dev.read_loop():
                if self.stop_event.is_set():
                    print("[KeypadListener] Ricevuto segnale di stop.")
                    break
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    is_down = (key_event.keystate == key_event.key_down)
                    # La callback riceve: scancode, keycode (es. "KEY_A"), is_down (bool)
                    self.midi_callback(key_event.scancode, str(key_event.keycode), is_down)
        except Exception as e:
            print(f"[KeypadListener] Errore: {e}")