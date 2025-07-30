from footswitch_lookup import FOOTSWITCH_LOOKUP
from tabs_lookup import TABS_LOOKUP
from custom_sysex_lookup import CUSTOM_SYSEX_LOOKUP
from sysex_utils import (
    send_sysex_to_ketron,
    sysex_tabs,
    sysex_footswitch_std,
    sysex_footswitch_ext,
    sysex_custom,
)
import mido

_last_msb = None
_last_lsb = None

def filter_and_translate_fantom_msg(msg, ketron_outport, state_manager, armonix_enabled=True, state="ready", verbose=False):
    global _last_msb, _last_lsb

    # --- NOTE ON/OFF ---
    if msg.type in ("note_on", "note_off"):
        if msg.channel == 0:
            ketron_outport.send(msg)
            if verbose:
                print(f"[FANTOM-FILTER] Inviato inalterato: {msg}")
        elif armonix_enabled and msg.type == "note_on":
            if msg.velocity == 1:
                name = footswitch_lookup_name(msg.note)
                if name:
                    for v in [0x7F, 0x00]:  # ON/OFF
                        data = sysex_footswitch_std(FOOTSWITCH_LOOKUP[name], v)
                        send_sysex_to_ketron(ketron_outport, data)
                    if verbose:
                        print(f"[FANTOM-FILTER] Footswitch std: {name} note={msg.note}")
            elif msg.velocity == 2:
                name = footswitch_lookup_name(msg.note + 128)
                if name:
                    for v in [0x7F, 0x00]:
                        data = sysex_footswitch_ext(FOOTSWITCH_LOOKUP[name] + 128, v)
                        send_sysex_to_ketron(ketron_outport, data)
                    if verbose:
                        print(f"[FANTOM-FILTER] Footswitch ext: {name} note={msg.note+128}")
            elif msg.velocity == 3:
                name = tabs_lookup_name(msg.note)
                if name:
                    for v in [0x7F, 0x00]:
                        data = sysex_tabs(TABS_LOOKUP[name], v)
                        send_sysex_to_ketron(ketron_outport, data)
                    if verbose:
                        print(f"[FANTOM-FILTER] Tabs: {name} note={msg.note}")
            else:
                if verbose:
                    print(f"[FANTOM-FILTER] Ignorato note_on velocity={msg.velocity}, note={msg.note}, channel={msg.channel}")

    # --- CONTROL CHANGE ---
    elif msg.type == "control_change" and armonix_enabled:
        if msg.control == 0:
            _last_msb = msg.value
            if verbose:
                print(f"[FANTOM-FILTER] Salvato MSB: {_last_msb}")
        elif msg.control == 32:
            _last_lsb = msg.value
            if verbose:
                print(f"[FANTOM-FILTER] Salvato LSB: {_last_lsb}")
        elif 0x15 <= msg.control <= 0x25:
            new_control = msg.control + 81
            cc_msg = msg.copy(channel=0, control=new_control)
            ketron_outport.send(cc_msg)
            if verbose:
                print(f"[FANTOM-FILTER] Slider filtrato e inviato: {cc_msg}")
        elif msg.control == 40:
            name = "Art. Toggle"
            val = 0x7F if msg.value == 127 else 0x00
            if name in FOOTSWITCH_LOOKUP:
                data = sysex_footswitch_ext(FOOTSWITCH_LOOKUP[name], val)
                send_sysex_to_ketron(ketron_outport, data)
                if verbose:
                    print(f"[FANTOM-FILTER] S1 switch: {name} note={msg}")
        elif msg.control == 41:
            name = "VOICETR.ON/OFF"
            val = 0x7F if msg.value == 127 else 0x00
            if name in FOOTSWITCH_LOOKUP:
                data = sysex_footswitch_std(FOOTSWITCH_LOOKUP[name], val)
                send_sysex_to_ketron(ketron_outport, data)
                if verbose:
                    print(f"[FANTOM-FILTER] S2 switch: {name} note={msg}")
        else:
            ketron_outport.send(msg)
            if verbose:
                print(f"[FANTOM-FILTER] CC inalterato: {msg}")

    # --- PROGRAM CHANGE ---
    elif msg.type == "program_change" and armonix_enabled:
        msb = _last_msb if _last_msb is not None else 0
        lsb = _last_lsb if _last_lsb is not None else 0
        key = (msb, lsb, msg.program)
        if verbose:
            print(f"[FANTOM-FILTER] Program Change tripletta: MSB={msb}, LSB={lsb}, PC={msg.program}")

        # --- se sono sul canale 15 attivo e disattivo ---
        if msg.channel == 15:
            if (msb == 85 and lsb == 3 and msg.program <= 3):
                if verbose:
                    print("[FANTOM-FILTER] Ricevuta attivazione.")
                state_manager.system_pause_off()
            else:
                if verbose:
                    print("[FANTOM-FILTER] Ricevuta PAUSA")
                state_manager.system_pause_on()
        else:
            action_num = program_change_mapping().get(key)
            if action_num:
                key_pressed(action_num, ketron_outport.name, verbose)
                if verbose:
                    print(f"[FANTOM-FILTER] Azione {action_num} inviata da program change {key}")
            else:
                if verbose:
                    print(f"[FANTOM-FILTER] Program Change {key} non mappato, ignorato")
    else:
        ketron_outport.send(msg)
        if verbose:
            print(f"[FANTOM-FILTER] msg inalterato: {msg}")


# --- HELPERS ---

def footswitch_lookup_name(note):
    for name, value in FOOTSWITCH_LOOKUP.items():
        if value == note:
            return name
    return None

def tabs_lookup_name(note):
    for name, value in TABS_LOOKUP.items():
        if value == note:
            return name
    return None

def program_change_mapping():
    return {
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

def key_pressed(val, ketron_port_name, verbose):
    # Placeholder: aggiungi la tua azione qui per ogni valore (1-16)
    if verbose:
        print(f"[FANTOM-FILTER] Key_pressed chiamato con {val} -- azione da implementare")
