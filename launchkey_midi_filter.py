from pathlib import Path
import json

from footswitch_lookup import FOOTSWITCH_LOOKUP
from tabs_lookup import TABS_LOOKUP
from sysex_utils import send_sysex_to_ketron, sysex_footswitch_std, sysex_tabs
import mido

"""
launchkey_config.json structure::
{
  "footswitch": {"<note>": "<FOOTSWITCH_NAME>"},
  "tabs": {"<note>": "<TABS_NAME>"},
  "program_change": {"MSB,LSB,PC": <action_number>}
}
- <note> is the MIDI note number sent by the Launchkey.
- Names must exist in footswitch_lookup.py or tabs_lookup.py.
- Program-change triples map to an arbitrary action number handled by
  ``key_pressed``.
"""

CONFIG = json.load(open(Path(__file__).with_name('launchkey_config.json')))

_last_msb = None
_last_lsb = None

def filter_and_translate_launchkey_msg(msg, ketron_outport, state_manager=None, armonix_enabled=True, verbose=False):
    global _last_msb, _last_lsb

    if msg.type == "note_on" and armonix_enabled:
        note_key = str(msg.note)
        if note_key in CONFIG.get("footswitch", {}):
            name = CONFIG["footswitch"][note_key]
            status = 0x7F if msg.velocity else 0x00
            data = sysex_footswitch_std(FOOTSWITCH_LOOKUP[name], status)
            send_sysex_to_ketron(ketron_outport, data)
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Footswitch {name} note={msg.note}")
            return
        if note_key in CONFIG.get("tabs", {}):
            name = CONFIG["tabs"][note_key]
            status = 0x7F if msg.velocity else 0x00
            data = sysex_tabs(TABS_LOOKUP[name], status)
            send_sysex_to_ketron(ketron_outport, data)
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Tab {name} note={msg.note}")
            return

    elif msg.type == "control_change" and armonix_enabled:
        if msg.control == 0:
            _last_msb = msg.value
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Salvato MSB: {_last_msb}")
            return
        if msg.control == 32:
            _last_lsb = msg.value
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Salvato LSB: {_last_lsb}")
            return

    elif msg.type == "program_change" and armonix_enabled:
        msb = _last_msb if _last_msb is not None else 0
        lsb = _last_lsb if _last_lsb is not None else 0
        key = f"{msb},{lsb},{msg.program}"
        action = CONFIG.get("program_change", {}).get(key)
        if action:
            key_pressed(action, ketron_outport.name, verbose)
            if verbose:
                print(f"[LAUNCHKEY-FILTER] Program Change {key} -> {action}")
            return

    ketron_outport.send(msg)
    if verbose:
        print(f"[LAUNCHKEY-FILTER] msg inalterato: {msg}")

def key_pressed(val, ketron_port_name, verbose):
    if verbose:
        print(f"[LAUNCHKEY-FILTER] key_pressed chiamato con {val} -- azione da implementare")
