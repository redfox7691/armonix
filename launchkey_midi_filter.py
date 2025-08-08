import json
import os
from tabs_lookup import TABS_LOOKUP
from footswitch_lookup import FOOTSWITCH_LOOKUP
from custom_sysex_lookup import CUSTOM_SYSEX_LOOKUP
from sysex_utils import (
    send_sysex_to_ketron,
    sysex_tabs,
    sysex_footswitch_std,
    sysex_footswitch_ext,
    sysex_custom,
)

# Load configuration for Launchkey mappings
_base_dir = os.path.dirname(os.path.abspath(__file__))
_config_path = os.path.join(_base_dir, "launchkey_config.json")
with open(_config_path) as f:
    LAUNCHKEY_CONFIG = json.load(f)

def _resolve_and_send(mapping, is_down, ketron_outport, verbose=False):
    cmd_type = mapping.get("type")
    name = mapping.get("name")
    status = 0x7F if is_down else 0x00
    data_bytes = None

    if cmd_type == "FOOTSWITCH":
        value = FOOTSWITCH_LOOKUP.get(name)
        if value is None:
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Footswitch '{name}' non trovato")
            return
        if value > 0x7F:
            data_bytes = sysex_footswitch_ext(value, status)
        else:
            data_bytes = sysex_footswitch_std(value, status)
    elif cmd_type == "TABS":
        value = TABS_LOOKUP.get(name)
        if value is None:
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Tabs '{name}' non trovato")
            return
        data_bytes = sysex_tabs(value, status)
    elif cmd_type == "CUSTOM":
        custom = CUSTOM_SYSEX_LOOKUP.get(name)
        if not custom:
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Custom Sysex '{name}' non trovato")
            return
        param = custom["switch_map"]["toggle"] if is_down else custom["switch_map"]["off"]
        data_bytes = sysex_custom(custom["format"], param)
    else:
        if verbose:
            print(f"[LAUNCHKEY-FILTER] Tipo comando '{cmd_type}' non gestito")
        return

    if verbose:
        print(f"[LAUNCHKEY-FILTER] Traduzione: tipo={cmd_type}, nome={name}, sysex={data_bytes}")
    send_sysex_to_ketron(ketron_outport, data_bytes)

def filter_and_translate_launchkey_msg(msg, ketron_outport, state_manager, armonix_enabled=True, state="ready", verbose=False):
    if not armonix_enabled:
        ketron_outport.send(msg)
        if verbose:
            print(f"[LAUNCHKEY-FILTER] Armonix disabilitato, inoltro: {msg}")
        return

    mapping = None
    is_down = False

    if msg.type in ("note_on", "note_off"):
        key = f"NOTE_{msg.note}"
        mapping = LAUNCHKEY_CONFIG.get(key)
        is_down = msg.type == "note_on" and msg.velocity > 0
    elif msg.type == "control_change":
        key = f"CC_{msg.control}"
        mapping = LAUNCHKEY_CONFIG.get(key)
        is_down = msg.value >= 64
    else:
        ketron_outport.send(msg)
        if verbose:
            print(f"[LAUNCHKEY-FILTER] Messaggio inalterato: {msg}")
        return

    if not mapping:
        ketron_outport.send(msg)
        if verbose:
            print(f"[LAUNCHKEY-FILTER] Nessuna mappatura per {msg}")
        return

    _resolve_and_send(mapping, is_down, ketron_outport, verbose=verbose)
