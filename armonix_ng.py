#!/home/b0/armonix/venv/bin/python
# v 1.0 25/01/2025
#       Funzionalità complete
import mido
import threading
import time
import os
from evdev import InputDevice, categorize, ecodes
import threading
from PyQt5 import QtWidgets, QtGui, QtCore
import sys

# Led su sfondo trasparente
class LedBar(QtWidgets.QWidget):
    def __init__(self, states_getter):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(900, 38, 120, 38)  # Modifica posizione/dimensione come vuoi
        self.led_letters = ['F', 'E', 'K', 'B', 'X']
        self.states_getter = states_getter
        self.show()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(500)  # aggiorna ogni mezzo secondo

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        states = self.states_getter()
        for i, state in enumerate(states):
            x = 10 + i * 22
            color = QtGui.QColor('green') if state else QtGui.QColor('black')
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtCore.Qt.white)
            painter.drawEllipse(x, 8, 20, 20)
            painter.setPen(QtCore.Qt.white if state else QtCore.Qt.black)
            painter.setFont(QtGui.QFont('Arial', 12, QtGui.QFont.Bold))
            painter.drawText(x + 5, 23, self.led_letters[i])

# Variabili globali
DEBUG = False
LEDRUN = True
armonix_enabled = False
awaiting_bank_select_fine = False
awaiting_program_change = False
last_msb = None
last_lsb = None
key_msb = None
key_lsb = None
bluetooth_connected = False
keypad_connected = False
bluetooth_state = None  # Inizializzazione corretta
keypad_state = None     # Inizializzazione corretta
stop_threads = False
fast_slow = 127 

# Template per messaggi SysEx (ottimizzazione)
sysex_template = mido.Message('sysex', data=[])

def get_led_states():
    return [
        bool(find_port("FANTOM")),            # Fantom 07
        bool(find_port("MIDI Gadget")),       # Ketron EVM
        bool(find_usbdev()),                  # Keyb USB
        bool(bluetooth_connected),            # iPad BLE
        bool(armonix_enabled),                # Armonix
    ]

def find_port(keyword):
    """Trova una porta MIDI contenente una parola chiave."""
    for port_name in mido.get_input_names():
        if keyword in port_name:
            return port_name
    return None

# Tastierino USB (modificato per Mint)
def find_usbdev():
    byid = "/dev/input/by-id/"
    try:
        for entry in os.listdir(byid):
            if "-event-kbd" in entry:
                return os.path.join(byid, entry)
    except FileNotFoundError:
        pass
    return None

def debug_print(message):
    """Stampa messaggi di debug se DEBUG è abilitato."""
    if DEBUG:
        print(message)

def send_sysex_message(note, is_extended, is_on, output_port):
    value = 0x7F if is_on else 0x00
    note = note & 0x7F
    if is_extended:
        sysex_data = [0x26, 0x79, 0x05, 0x01, note, value]
    else:
        sysex_data = [0x26, 0x79, 0x03, note, value]
    sysex_template.data = sysex_data  # Modifica il template
    output_port.send(sysex_template)  # Invia il template
    debug_print(f"SysEx inviato: {sysex_data}")

def send_sysex_message_tabs(note, is_on, output_port):
    value = 0x7F if is_on else 0x00
    note = note & 0x7F
    sysex_data = [0x26, 0x7C, note, value]
    sysex_template.data = sysex_data
    output_port.send(sysex_template)
    debug_print(f"SysEx TABS inviato: {sysex_data}")

# Gestione delle note
def process_note_message(message, output_port):
    debug_print(f"Nota ricevuta: {message}")
    if message.channel == 0:  # Canale 1 passa inalterato
        output_port.send(message)
        debug_print(f"Inviato inalterato: {message}")
    # cambio di logica: non conta il canale, ma conta la velocity:
    # 1 = sysex normale
    # 2 = sysex esteso
    # 3 = sysex tabs
    # al rilascio il Fantom07 è sempre alla velocità 64, quindi devo fare sempre il doppio messaggio on/off
    #elif message.channel % 2 == 1:  # Canali pari: SysEx normale
    #    send_sysex_message(message.note, is_extended=False, is_on=(message.type == 'note_on'), output_port=output_port)
    #elif message.channel % 2 == 0:  # Canali dispari: SysEx esteso
    #    send_sysex_message(message.note, is_extended=True, is_on=(message.type == 'note_on'), output_port=output_port)
    elif message.velocity == 1:
        send_sysex_message(message.note, is_extended=False, is_on=True, output_port=output_port)
        send_sysex_message(message.note, is_extended=False, is_on=False, output_port=output_port)
    elif message.velocity == 2:
        send_sysex_message(message.note, is_extended=True, is_on=True, output_port=output_port)
        send_sysex_message(message.note, is_extended=False, is_on=False, output_port=output_port)
    elif message.velocity == 3:
        send_sysex_message_tabs(message.note, is_on=True, output_port=output_port)
        send_sysex_message_tabs(message.note, is_on=False, output_port=output_port)

# Gestione dei Control Change
def process_control_change(message, output_port):
    global last_msb, last_lsb, key_msb, key_lsb, awaiting_program_change, awaiting_bank_select_fine, fast_slow
    debug_print(f"Control Change ricevuto: {message}")

    # Controllo sul canale 1: trasmetti tutto se armonix_enabled è True
    if message.channel == 0 and armonix_enabled:
        if message.control == 0:
            key_msb = message.value
            debug_print(f"Ricevuto MSB sul canale 1: {key_msb}")
        elif message.control == 32:
            key_lsb = message.value
            debug_print(f"Ricevuto LSB sul canale 1: {key_lsb}")
        elif 0x15 <= message.control <= 0x25:  # Filtra CC specifici
            new_control = message.control + 81
            new_message = mido.Message('control_change', channel=0, control=new_control, value=message.value)
            output_port.send(new_message)
            debug_print(f"Control Change filtrato e inviato: {new_message}")
        # Controllo per S1 e S2
        elif message.control == 40:  # S1
            if message.value == 127:  # Premuto
                sysex_msg = send_sysex_message(fast_slow, is_extended=False, is_on=True, output_port=output_port)
                #output_port.send(sysex_msg)
                debug_print(f"S1 premuto: SysEx inviato: {sysex_msg}")
            elif message.value == 0:  # Rilasciato
                sysex_msg = send_sysex_message(fast_slow, is_extended=False, is_on=False, output_port=output_port)
                #output_port.send(sysex_msg)
                debug_print(f"S1 rilasciato: SysEx inviato: {sysex_msg}")
                #al rilascio lo cambio
                if fast_slow == 127:
                    fast_slow = 126
                else:
                    fast_slow = 127
        elif message.control == 41:  # S2
            if message.value == 127:  # Premuto
                sysex_msg = send_sysex_message(61, is_extended=False, is_on=True, output_port=output_port)
                #output_port.send(sysex_msg)
                debug_print(f"S2 premuto: SysEx inviato: {sysex_msg}")
            elif message.value == 0:  # Rilasciato
                sysex_msg = send_sysex_message(61, is_extended=False, is_on=False, output_port=output_port)
                #output_port.send(sysex_msg)
                debug_print(f"S2 rilasciato: SysEx inviato: {sysex_msg}")
        else:
            output_port.send(message)
            debug_print(f"Control Change inviato inalterato: {message}")
        return

    # Filtra slider (CC 0x15 - 0x25) per altri canali
    if armonix_enabled and 0x15 <= message.control <= 0x25:
        new_control = message.control + 81
        new_message = mido.Message('control_change', channel=0, control=new_control, value=message.value)
        output_port.send(new_message)
        debug_print(f"Control Change filtrato per slider e inviato: {new_message}")
        return

    if message.control == 0:  # MSB
        last_msb = message.value
        awaiting_bank_select_fine = True
        debug_print(f"Salvato MSB: {last_msb}, in attesa del LSB.")
    elif message.control == 32:  # LSB
        last_lsb = message.value
        if awaiting_bank_select_fine and last_msb == 85 and last_lsb == 3:
            awaiting_program_change = True
            awaiting_bank_select_fine = False
            debug_print("Ricevuto LSB 3, in attesa del Program Change.")
    debug_print(f"Stato: awaiting_bank_select_fine={awaiting_bank_select_fine}, awaiting_program_change={awaiting_program_change}")

# Mappatura Program Change a tasti
def on_sequence_recognized(msb, lsb, program, output_port):
    debug_print(f"Program Change riconosciuto: MSB={msb}, LSB={lsb}, Program={program}")
    mapping = {
        (0x69, 0x00, 0x7F): 1,
        (0x69, 0x01, 0x7F): 2,
        (0x57, 0x42, 0x34): 3,
        (0x57, 0x42, 0x2C): 4,
        (0x57, 0x5D, 0x4E): 5,
        (0x57, 0x41, 0x09): 6,
        (0x59, 0x41, 0x00): 7,
        (0x57, 0x42, 0x09): 8,
        (0x59, 0x41, 0x37): 9,
        (0x59, 0x41, 0x0A): 10,
        (0x57, 0x5C, 0x42): 11,
        (0x57, 0x5C, 0x18): 12,
        (0x57, 0x5C, 0x7D): 13,
        (0x56, 0x40, 0x00): 14,
        (0x59, 0x00, 0x00): 15,
        (0x56, 0x00, 0x00): 16,
    }
    if (msb, lsb, program) in mapping:
        key_pressed(mapping[(msb, lsb, program)], output_port)

# Azioni per tasti
def key_pressed(val, output_port):
    global LEDRUN
    actions = {
        1: 'led_on',
        2: 'led_off',
        3: 'mic_echo_on',  # Abilita Echo su mic1
        4: 'mic_echo_off', # Disabilita Echo su mic1
        5: 'mic_echo_pre', # Mono
        6: 'mic_echo_pre', # Stereo
        7: 'mic_echo_pre', # Triplet
        8: 'mic_echo_pre', # Multitap
        9: 'mic_echo_pre', # Reflection
        10: 'mic_echo_pre',# Stage
        11: 'mic_echo_pre',# PingPong
        12: 'mic_echo_pre',# EchoTap
        13: 51, # EXIT
        14: 51, # EXIT
        15: 51, # EXIT
        16: 51  # EXIT
    }
    debug_print(f"Tasto premuto: {val}")
    try:
        action = actions[val]
        if action == 'led_off':
            LEDRUN = False
        elif action == 'led_on':
            LEDRUN = True
        elif action == 'mic_echo_off':
            sysex_data = [0x26, 0x7B, 0x25, 0x05, 0x00]
            sysex_template.data = sysex_data
            output_port.send(sysex_template)
            debug_print(f"SysEx Echo MIC OFF inviato: {sysex_data}")
        elif action == 'mic_echo_on':
            sysex_data = [0x26, 0x7B, 0x25, 0x05, 0x01]
            sysex_template.data = sysex_data
            output_port.send(sysex_template)
            debug_print(f"SysEx Echo MIC ON inviato: {sysex_data}")
        elif action == 'mic_echo_pre':
            # NRPN
            # CC 0x63 xx CC 0x62 yy CC 0x06 val
            # per echo mic: xx=0x70 yy=0x30
            preset = val - 2 # i tasti da 3 a 12 diventano da 1 a 8
            ch = 0x01 # da impostare il canale 2 sulle preferenze del Ketron
            msg = mido.Message('control_change',channel=ch,control=0x63,value=0x70)
            output_port.send(msg)
            debug_print(f"MSG inviato: {msg}")
            msg = mido.Message('control_change',channel=ch,control=0x62,value=0x30)
            output_port.send(msg)
            debug_print(f"MSG inviato: {msg}")
            msg = mido.Message('control_change',channel=ch,control=0x06,value=val)
            output_port.send(msg)
            debug_print(f"MSG inviato: {msg}")
        else:
            send_sysex_message(action, is_extended=False, is_on=True, output_port=output_port)
            send_sysex_message(action, is_extended=False, is_on=False, output_port=output_port)
    except KeyError:
        debug_print(f"Chiave non valida: {val}")

# Gestione messaggi MIDI
def process_message(message, output_port):
    global armonix_enabled, awaiting_program_change, last_msb, last_lsb, key_msb, key_lsb

    # Debug del messaggio ricevuto
    debug_print(f"Messaggio ricevuto: {message}")

    # Gestione attivazione Armonix
    if message.channel == 15:
        if message.type == 'control_change':
            process_control_change(message, output_port)
            return
        elif message.type == 'program_change':
            # voglio attivare armonix selezionado una delle prime 4 scene della zona D (0,1,2,3)
            if awaiting_program_change and last_msb == 85 and last_lsb == 3 and message.program <= 3:
                awaiting_program_change = False
                armonix_enabled = True
                debug_print("Armonix attivato!")
                return
            elif armonix_enabled:
                armonix_enabled = False
                debug_print("Armonix disattivato! Banco cambiato.")
                return
        debug_print(f"Stato finale: armonix_enabled={armonix_enabled}, awaiting_program_change={awaiting_program_change}")

    # Processa i messaggi solo se Armonix è abilitato
    if not armonix_enabled:
        debug_print(f"Armonix disabilitato. Ignorato: {message}")
        return

    # Trasmetti messaggi sul canale 1 inalterati, eccetto CC filtrati
    if message.channel == 0:
        if message.type == 'control_change':
            process_control_change(message, output_port)
        elif message.type == 'program_change':
            on_sequence_recognized(key_msb, key_lsb, message.program, output_port)
        else:
            output_port.send(message)
            debug_print(f"Messaggio inviato inalterato: {message}")
        return

    if message.type == 'note_on' or message.type == 'note_off':
        process_note_message(message, output_port)
    elif message.type == 'control_change':
        process_control_change(message, output_port)
    elif message.type == 'program_change' and message.channel == 0:
        on_sequence_recognized(last_msb, last_lsb, message.program, output_port)

def wait_for_ports():
    """Aspetta che le porte MIDI necessarie siano disponibili."""
    fantom_port, ketron_port = None, None
    while not (fantom_port and ketron_port):
        fantom_port = find_port("FANTOM-06 07")
        ketron_port = find_port("MIDI Gadget")
        if not fantom_port:
            debug_print("In attesa della connessione al Fantom...")
        if not ketron_port:
            debug_print("In attesa della connessione al Ketron...")
        time.sleep(1)  # Aspetta prima di riprovare
    return fantom_port, ketron_port

def open_port_safely(port_name, port_type="input"):
    """Apre una porta MIDI in modo sicuro."""
    if port_name:
        try:
            if port_type == "input":
                return mido.open_input(port_name)
            elif port_type == "output":
                return mido.open_output(port_name)
        except Exception as e:
            debug_print(f"Errore nell'apertura della porta {port_name}: {e}")
    return None


# Modifichiamo la gestione degli stati dei thread
class ThreadState:
    def __init__(self):
        self.thread = None
        self.running = False
        self.initialized = False

bluetooth_state = ThreadState()
keypad_state = ThreadState()

def monitor_bluetooth(output_ketron):
    """Monitora continuamente la connessione Bluetooth e gestisce i messaggi se disponibile."""
    global bluetooth_connected
    last_bt_check = time.time()
    try:
        while bluetooth_state.running:
            try:
                current_time = time.time()
                # Cerchiamo la porta Bluetooth
                if current_time - last_bt_check >= 10:
                    bt_port = find_port("Bluetooth")
                    last_bt_check = current_time
                else:
                    bt_port = find_port("Bluetooth")
                if bt_port:
                    with mido.open_input(bt_port) as input_bt:
                        bluetooth_connected = True
                        debug_print(f"Bluetooth connesso su {bt_port}")
                        while bluetooth_state.running:
                            try:
                                for msg in input_bt.iter_pending():
                                    debug_print(f"Messaggio ricevuto da Bluetooth: {msg}")
                                    output_ketron.send(msg)
                                time.sleep(0.001)
                            except Exception as e:
                                debug_print(f"Errore nella lettura Bluetooth: {e}")
                                break
            except Exception as e:
                debug_print(f"Errore nella gestione del Bluetooth: {e}")
            finally:
                bluetooth_connected = False
            if bluetooth_state.running:
                time.sleep(1)
    finally:
        bluetooth_state.initialized = False
        debug_print("Thread Bluetooth terminato")

def monitor_bluetooth_old(output_ketron):
    """Monitora continuamente la connessione Bluetooth e gestisce i messaggi se disponibile."""
    global bluetooth_connected
    last_bt_check = time.time()   
    try:
        while bluetooth_state.running:
            try:
                current_time = time.time()
                if current_time - last_bt_check >= 10: #Controlla ogni 10 secondi
                    bt_port = find_port("RP3-Bluetooth")
                    last_bt_check = current_time
                else:
                    bt_port = find_port("RP3-Bluetooth")
                if bt_port:
                    with mido.open_input(bt_port) as input_bt:
                        bluetooth_connected = True
                        debug_print(f"Bluetooth connesso su {bt_port}")
                        while bluetooth_state.running:
                            try:
                                for msg in input_bt.iter_pending():
                                    debug_print(f"Messaggio ricevuto da Bluetooth: {msg}")
                                    output_ketron.send(msg)
                                time.sleep(0.001)
                            except Exception as e:
                                debug_print(f"Errore nella lettura Bluetooth: {e}")
                                break
            except Exception as e:
                debug_print(f"Errore nella gestione del Bluetooth: {e}")
            finally:
                bluetooth_connected = False
            if bluetooth_state.running:
                time.sleep(1)
    finally:
        bluetooth_state.initialized = False
        debug_print("Thread Bluetooth terminato")

def handle_keypad(device_path, output_port):
    from evdev import InputDevice, categorize, ecodes
    try:
        device = InputDevice(device_path)
        actions = { # Mappatura tasti
            'KEY_A': 15, 'KEY_B': 16,  'KEY_C': 17, 'KEY_D': 23,
            'KEY_E': 22, 'KEY_F': 120, 'KEY_G': 80, 'KEY_H': 160,
            'KEY_I': 3,  'KEY_L': 4,   'KEY_M': 5,  'KEY_N': 6,
            'KEY_O': 32, 'KEY_P': 50,  'KEY_Q': 31,
            'KEY_R': 20, 'KEY_S': 18,  'KEY_T': 19,
        }
        debug_print(f"Listening to {device.name}")
        for event in device.read_loop():
            if stop_threads:
                break
            if event.type == ecodes.EV_KEY:
                key_event = categorize(event)
                # Ottimizzazione: accesso diretto al valore della chiave
                keycode = key_event.keycode
                if isinstance(keycode, list): #questo non serve, ma lo lascio per compatibilità
                    keycode = keycode[0]
                try:
                    note = actions[keycode] # Accesso diretto al dizionario
                    ext = note > 127
                    if ext:
                        note -= 128
                    if key_event.keystate == 1:
                        send_sysex_message(note, is_extended=ext, is_on=True, output_port=output_port)
                    elif key_event.keystate == 0:
                        send_sysex_message(note, is_extended=ext, is_on=False, output_port=output_port)
                except KeyError:
                    debug_print(f"Keycode non mappato: {keycode}") #gestisco l'errore di keycode non presente
    except Exception as e:
        debug_print(f"Errore nella lettura del keypad: {e}")

def monitor_keypad(output_ketron):
    """Monitora continuamente la connessione del tastierino USB."""
    global keypad_connected
    
    try:
        while keypad_state.running:
            try:
                usb_device = find_usbdev()
                if usb_device:
                    keypad_connected = True
                    handle_keypad(usb_device, output_ketron)
            except Exception as e:
                debug_print(f"Errore nella gestione del tastierino USB: {e}")
            finally:
                keypad_connected = False
            if keypad_state.running:
                time.sleep(1)
    finally:
        keypad_state.initialized = False
        debug_print("Thread Keypad terminato")

def cleanup_threads():
    """Pulisce e termina i thread in modo sicuro."""
    debug_print("Iniziata pulizia dei thread...")
    
    # Ferma il thread Bluetooth
    if bluetooth_state.initialized:
        debug_print("Arresto thread Bluetooth...")
        bluetooth_state.running = False
        if bluetooth_state.thread and bluetooth_state.thread.is_alive():
            try:
                bluetooth_state.thread.join(timeout=1.0)
            except Exception as e:
                debug_print(f"Errore durante l'arresto del thread Bluetooth: {e}")
    bluetooth_state.thread = None
    bluetooth_state.initialized = False
    
    # Ferma il thread Keypad
    if keypad_state.initialized:
        debug_print("Arresto thread Keypad...")
        keypad_state.running = False
        if keypad_state.thread and keypad_state.thread.is_alive():
            try:
                keypad_state.thread.join(timeout=1.0)
            except Exception as e:
                debug_print(f"Errore durante l'arresto del thread Keypad: {e}")
    keypad_state.thread = None
    keypad_state.initialized = False
    
    debug_print("Pulizia dei thread completata")

def start_threads(output_ketron):
    """Avvia i thread in modo sicuro."""
    # Avvia il thread Bluetooth
    if not bluetooth_state.initialized:
        try:
            bluetooth_state.running = True
            bluetooth_state.thread = threading.Thread(target=monitor_bluetooth, args=(output_ketron,))
            bluetooth_state.thread.daemon = True
            bluetooth_state.thread.start()
            bluetooth_state.initialized = True
            debug_print("Thread Bluetooth avviato")
        except Exception as e:
            debug_print(f"Errore nell'avvio del thread Bluetooth: {e}")
            bluetooth_state.running = False
    
    # Avvia il thread Keypad
    if not keypad_state.initialized:
        try:
            keypad_state.running = True
            keypad_state.thread = threading.Thread(target=monitor_keypad, args=(output_ketron,))
            keypad_state.thread.daemon = True
            keypad_state.thread.start()
            keypad_state.initialized = True
            debug_print("Thread Keypad avviato")
        except Exception as e:
            debug_print(f"Errore nell'avvio del thread Keypad: {e}")
            keypad_state.running = False

def main():
    global bluetooth_state, keypad_state # Dichiarazione globale
    bluetooth_state = ThreadState()  # Inizializzazione corretta
    keypad_state = ThreadState()     # Inizializzazione corretta    
    armonix_enabled_last = None 
    last_midi_port_check = time.time()
    last_thread_check = last_midi_port_check

    # Avvia il thread di stato
    #threading.Thread(target=print_status, daemon=True).start()
    #threading.Thread(target=print_status_led, daemon=True).start()

    while True:
        try:
            fantom_port, ketron_port = wait_for_ports()
            
            input_fantom = open_port_safely(fantom_port, "input")
            output_ketron = open_port_safely(ketron_port, "output")

            if not input_fantom or not output_ketron:
                debug_print("Errore: impossibile aprire le porte necessarie. Riprovo...")
                cleanup_threads()
                if input_fantom:
                    input_fantom.close()
                if output_ketron:
                    output_ketron.close()
                time.sleep(1)
                continue

            debug_print(f"Collegato a {fantom_port} e {ketron_port}")

            # Avvia i thread
            start_threads(output_ketron)

            while True:
                time.sleep(.0001)
                if armonix_enabled_last != armonix_enabled:
                    armonix_enabled_last = armonix_enabled
                
                # Verifica connessioni MIDI
                if time.time() - last_midi_port_check >= 10: # controllo ogni 10 secondi
                    last_midi_port_check = time.time() 
                    if fantom_port not in mido.get_input_names() or ketron_port not in mido.get_output_names():
                        debug_print("Connessione persa con uno dei dispositivi. Riavvio delle connessioni...")
                        raise ConnectionError("Dispositivo disconnesso")

                # Verifica stato dei thread
                if time.time() - last_thread_check >= 3: # controllo ogni 3 secondi
                    last_thread_check = time.time()
                    if (bluetooth_state.initialized and not bluetooth_state.thread.is_alive()) or \
                       (keypad_state.initialized and not keypad_state.thread.is_alive()):
                        debug_print("Uno dei thread è terminato inaspettatamente. Riavvio...")
                        raise ConnectionError("Thread terminato")

                for msg in input_fantom.iter_pending():
                    process_message(msg, output_ketron)

        except ConnectionError as e:
            debug_print(f"Errore di connessione: {e}")
            cleanup_threads()
            if 'input_fantom' in locals() and input_fantom:
                input_fantom.close()
            if 'output_ketron' in locals() and output_ketron:
                output_ketron.close()
            time.sleep(1)
            continue

        except KeyboardInterrupt:
            debug_print("Interruzione manuale ricevuta. Uscita...")
            cleanup_threads()
            if 'input_fantom' in locals() and input_fantom:
                input_fantom.close()
            if 'output_ketron' in locals() and output_ketron:
                output_ketron.close()
            break

        except Exception as e:
            debug_print(f"Errore inaspettato: {e}")
            cleanup_threads()
            if 'input_fantom' in locals() and input_fantom:
                input_fantom.close()
            if 'output_ketron' in locals() and output_ketron:
                output_ketron.close()
            time.sleep(1)
            continue

if __name__ == "__main__":
    threading.Thread(target=main, daemon=True).start()
    app = QtWidgets.QApplication(sys.argv)
    w = LedBar(get_led_states)
    sys.exit(app.exec_())
