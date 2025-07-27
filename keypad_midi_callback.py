import json
from tabs_lookup import TABS_LOOKUP
from footswitch_lookup import FOOTSWITCH_LOOKUP
from custom_sysex_lookup import CUSTOM_SYSEX_LOOKUP
from sysex_utils import send_sysex_to_ketron, sysex_tabs, sysex_footswitch_std, sysex_footswitch_ext, sysex_custom

with open("keypad_config.json") as f:
    KEYPAD_CONFIG = json.load(f)

def keypad_midi_callback(keycode, is_down, ketron_port_name, verbose=False):
    mapping = KEYPAD_CONFIG.get(keycode)
    if not mapping:
        if verbose:
            print(f"[VERBOSE] Tasto {keycode} non mappato")
        return

    cmd_type = mapping["type"]
    name = mapping["name"]
    data_bytes = None

    # Risolvi il comando e la stringa Sysex
    if cmd_type == "FOOTSWITCH":
        value = FOOTSWITCH_LOOKUP.get(name)
        if value is None:
            if verbose:
                print(f"[VERBOSE] FOOTSWITCH '{name}' non trovato")
            return
        status = 0x7F if is_down else 0x00
        if value > 0x7F:
            data_bytes = sysex_footswitch_ext(value, status)
        else:
            data_bytes = sysex_footswitch_std(value, status)

    elif cmd_type == "TABS":
        value = TABS_LOOKUP.get(name)
        if value is None:
            if verbose:
                print(f"[VERBOSE] TABS '{name}' non trovato")
            return
        status = 0x7F if is_down else 0x00
        data_bytes = sysex_tabs(value, status)

    elif cmd_type == "CUSTOM":
        custom = CUSTOM_SYSEX_LOOKUP.get(name)
        if not custom:
            if verbose:
                print(f"[VERBOSE] Custom Sysex '{name}' non trovato")
            return
        param = custom["switch_map"]["toggle"] if is_down else custom["switch_map"]["off"]
        data_bytes = sysex_custom(custom["format"], param)

    else:
        if verbose:
            print(f"[VERBOSE] Tipo comando '{cmd_type}' non gestito")
        return

    # Stampa verbose
    if verbose:
        print(f"[VERBOSE] Tasto {keycode}: tipo={cmd_type}, comando='{name}', sysex={data_bytes}")

    # Invia il sysex (solo se tutto è corretto)
    if data_bytes:
        send_sysex_to_ketron(ketron_port_name, data_bytes)