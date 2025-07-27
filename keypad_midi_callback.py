# keypad_midi_callback.py

import json
from tabs_lookup import TABS_LOOKUP
from footswitch_lookup import FOOTSWITCH_LOOKUP
from custom_sysex_lookup import CUSTOM_SYSEX_LOOKUP
from sysex_utils import send_sysex_to_ketron, sysex_tabs, sysex_footswitch_std, sysex_custom

with open("keypad_config.json") as f:
    KEYPAD_CONFIG = json.load(f)

def keypad_midi_callback(keycode, is_down, ketron_port_name):
    """
    Callback universale per il tastierino USB.
    - keycode: es. "KEY_A"
    - is_down: True se pressione tasto, False se rilascio
    - ketron_port_name: stringa nome porta MIDI Ketron
    """
    mapping = KEYPAD_CONFIG.get(keycode)
    if not mapping:
        print(f"Keycode {keycode} non mappato nel config")
        return

    msg_type = mapping["type"]
    name = mapping["name"]

    if msg_type == "FOOTSWITCH":
        value = FOOTSWITCH_LOOKUP.get(name)
        if value is None:
            print(f"FOOTSWITCH '{name}' non trovato")
            return
        status = 0x7F if is_down else 0x00
        data_bytes = sysex_footswitch_std(value, status)
        send_sysex_to_ketron(ketron_port_name, data_bytes)

    elif msg_type == "TABS":
        value = TABS_LOOKUP.get(name)
        if value is None:
            print(f"TABS '{name}' non trovato")
            return
        status = 0x7F if is_down else 0x00
        data_bytes = sysex_tabs(value, status)
        send_sysex_to_ketron(ketron_port_name, data_bytes)

    elif msg_type == "CUSTOM":
        custom = CUSTOM_SYSEX_LOOKUP.get(name)
        if not custom:
            print(f"Custom Sysex '{name}' non trovato")
            return
        # Per MICRO 1 ECHO SWITCH: key down -> toggle (0x7F), key up -> off (0x00)
        if is_down:
            param = custom["switch_map"]["toggle"]
        else:
            param = custom["switch_map"]["off"]
        data_bytes = sysex_custom(custom["format"], param)
        send_sysex_to_ketron(ketron_port_name, data_bytes)

    else:
        print(f"Tipo '{msg_type}' non gestito")