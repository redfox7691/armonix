import threading
from evdev import InputDevice, categorize, ecodes

class KeypadListener(threading.Thread):
    def __init__(self, device_path, midi_callback, stop_event, verbose=False):
        super().__init__()
        self.device_path = device_path
        self.midi_callback = midi_callback
        self.stop_event = stop_event
        self.verbose = verbose

    def run(self):
        try:
            dev = InputDevice(self.device_path)
            if self.verbose:
                print(f"[KeypadListener] In ascolto su {self.device_path}")
            for event in dev.read_loop():
                if self.stop_event.is_set():
                    if self.verbose:
                        print("[KeypadListener] Ricevuto segnale di stop.")
                    break
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    # La callback riceve: scancode, keycode (es. "KEY_A"), is_down (bool)
                    # Non dobbiamo prendere l'evento "key_repeat", ci interessano solo up e down
                    if key_event.keystate == key_event.key_down:
                        self.midi_callback(key_event.scancode, str(key_event.keycode), is_down=True)
                    elif key_event.keystate == key_event.key_up:
                        self.midi_callback(key_event.scancode, str(key_event.keycode), is_down=False)
        except Exception as e:
            if self.verbose:
                print(f"[KeypadListener] Errore: {e}")
