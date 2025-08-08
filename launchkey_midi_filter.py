import json
import os
from typing import Optional

import mido

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

# Load configuration
_base_dir = os.path.dirname(os.path.abspath(__file__))
_config_path = os.path.join(_base_dir, "launchkey_config.json")
if os.path.exists(_config_path):
    with open(_config_path, "r") as f:
        LAUNCHKEY_CONFIG = json.load(f)
else:
    LAUNCHKEY_CONFIG = {"notes": {}, "controls": {}}


def _resolve_mapping(mapping: dict, is_down: bool) -> Optional[list]:
    """Resolve mapping entry to sysex data bytes."""
    cmd_type = mapping.get("type")
    name = mapping.get("name")
    if cmd_type == "FOOTSWITCH":
        value = FOOTSWITCH_LOOKUP.get(name)
        if value is None:
            return None
        status = 0x7F if is_down else 0x00
        if value > 0x7F:
            return sysex_footswitch_ext(value, status)
        return sysex_footswitch_std(value, status)
    elif cmd_type == "TABS":
        value = TABS_LOOKUP.get(name)
        if value is None:
            return None
        status = 0x7F if is_down else 0x00
        return sysex_tabs(value, status)
    elif cmd_type == "CUSTOM":
        custom = CUSTOM_SYSEX_LOOKUP.get(name)
        if not custom:
            return None
        param = custom["switch_map"]["toggle" if is_down else "off"]
        return sysex_custom(custom["format"], param)
    return None


def filter_and_translate_msg(
    msg: mido.Message,
    ketron_outport,
    state_manager,
    armonix_enabled: bool = True,
    state: str = "ready",
    verbose: bool = False,
):
    """Filter and translate Launchkey MIDI messages according to configuration."""
    if not armonix_enabled:
        ketron_outport.send(msg)
        return

    if msg.type in ("note_on", "note_off"):
        mapping = LAUNCHKEY_CONFIG.get("notes", {}).get(str(msg.note))
        if mapping:
            is_down = msg.type == "note_on" and msg.velocity > 0
            data = _resolve_mapping(mapping, is_down)
            if data:
                send_sysex_to_ketron(ketron_outport, data)
                if verbose:
                    print(f"[LAUNCHKEY-FILTER] note {msg.note} -> {mapping['name']} {data}")
            else:
                if verbose:
                    print(f"[LAUNCHKEY-FILTER] note {msg.note} mapping unresolved")
        else:
            ketron_outport.send(msg)
            if verbose:
                print(f"[LAUNCHKEY-FILTER] note passthrough {msg}")

    elif msg.type == "control_change":
        mapping = LAUNCHKEY_CONFIG.get("controls", {}).get(str(msg.control))
        if mapping:
            is_down = msg.value > 0
            data = _resolve_mapping(mapping, is_down)
            if data:
                send_sysex_to_ketron(ketron_outport, data)
                if verbose:
                    print(f"[LAUNCHKEY-FILTER] cc {msg.control} -> {mapping['name']} {data}")
            else:
                if verbose:
                    print(f"[LAUNCHKEY-FILTER] cc {msg.control} mapping unresolved")
        else:
            ketron_outport.send(msg)
            if verbose:
                print(f"[LAUNCHKEY-FILTER] cc passthrough {msg}")

    else:
        ketron_outport.send(msg)
        if verbose:
            print(f"[LAUNCHKEY-FILTER] passthrough {msg}")
