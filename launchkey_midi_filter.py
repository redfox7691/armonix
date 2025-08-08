import json
import os
import re

import mido

from footswitch_lookup import FOOTSWITCH_LOOKUP
from tabs_lookup import TABS_LOOKUP
from sysex_utils import (
    send_sysex_to_ketron,
    sysex_tabs,
    sysex_footswitch_std,
    sysex_footswitch_ext,
)


# --- Config loading -------------------------------------------------------

base_dir = os.path.dirname(os.path.abspath(__file__))
_config_path = os.path.join(base_dir, "launchkey_config.json")


def _load_launchkey_filters(path):
    """Load launchkey_config.json stripping comments."""
    filters = {"NOTE": {}, "CC": {}}
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        cleaned = []
        for line in lines:
            line = re.sub(r"//.*", "", line)
            line = re.sub(r"#.*", "", line)
            cleaned.append(line)
        data = json.loads("".join(cleaned))
    except Exception:
        data = {}

    for entry in data.get("NOTE", []):
        chan = entry.get("channel")
        note = entry.get("note")
        if chan is None or note is None:
            continue
        filters["NOTE"].setdefault(chan, {})[note] = entry

    for entry in data.get("CC", []):
        chan = entry.get("channel")
        cc = entry.get("control")
        if chan is None or cc is None:
            continue
        filters["CC"].setdefault(chan, {})[cc] = entry

    return filters


LAUNCHKEY_FILTERS = _load_launchkey_filters(_config_path)


# --- Master port filter ---------------------------------------------------

def filter_and_translate_launchkey_msg(
    msg, ketron_outport, state_manager, armonix_enabled=True, state="ready", verbose=False
):
    """
    Forward Launchkey messages to the Ketron only when they are on MIDI channel 1
    (mido channel 0). Messages on other channels are ignored, optionally logging
    the event when ``verbose`` is enabled.
    """

    if msg.channel != 0:
        if verbose:
            print(f"[LAUNCHKEY-FILTER] Ignorato canale {msg.channel}: {msg}")
        return

    if armonix_enabled:
        ketron_outport.send(msg)
        if verbose:
            print(f"[LAUNCHKEY-FILTER] Inviato inalterato: {msg}")
    elif verbose:
        print(f"[LAUNCHKEY-FILTER] Bloccato: {msg}")


# --- DAW port filter ------------------------------------------------------

_ketron_outport = None


def filter_and_translate_launchkey_daw_msg(msg, daw_outport, state_manager, verbose=False):
    """Filtro dedicato per la porta DAW del Launchkey."""
    global _ketron_outport

    if _ketron_outport is None:
        try:
            _ketron_outport = mido.open_output(state_manager.ketron_port, exclusive=False)
            if verbose:
                print(f"[LAUNCHKEY-DAW-FILTER] Aperta porta Ketron: {_ketron_outport.name}")
        except Exception as e:
            if verbose:
                print(f"[LAUNCHKEY-DAW-FILTER] Errore apertura porta Ketron: {e}")
            return

    if verbose:
        print(f"[LAUNCHKEY-DAW-FILTER] Ricevuto: {msg}")

    rule = None

    if msg.type in ("note_on", "note_off"):
        rule = LAUNCHKEY_FILTERS["NOTE"].get(msg.channel, {}).get(getattr(msg, "note", None))
        if rule:
            is_on = msg.type == "note_on" and msg.velocity > 0
            status = 0x7F if is_on else 0x00
            rtype = rule.get("type")
            name = rule.get("name")
            if rtype == "FOOTSWITCH" and name in FOOTSWITCH_LOOKUP:
                val = FOOTSWITCH_LOOKUP[name]
                data = (
                    sysex_footswitch_ext(val, status)
                    if val > 0x7F
                    else sysex_footswitch_std(val, status)
                )
                send_sysex_to_ketron(_ketron_outport, data)
                if verbose:
                    print(f"[LAUNCHKEY-DAW-FILTER] NOTE -> FOOTSWITCH {name} {'ON' if is_on else 'OFF'}")
            elif rtype == "TABS" and name in TABS_LOOKUP:
                val = TABS_LOOKUP[name]
                data = sysex_tabs(val, status)
                send_sysex_to_ketron(_ketron_outport, data)
                if verbose:
                    print(f"[LAUNCHKEY-DAW-FILTER] NOTE -> TABS {name} {'ON' if is_on else 'OFF'}")
        elif verbose:
            print(
                f"[LAUNCHKEY-DAW-FILTER] Nessuna regola per nota {msg.note} canale {msg.channel}"
            )

    elif msg.type == "control_change":
        rule = LAUNCHKEY_FILTERS["CC"].get(msg.channel, {}).get(msg.control)
        if rule:
            rtype = rule.get("type")
            name = rule.get("name")
            if rtype in ("FOOTSWITCH", "TABS"):
                status = 0x7F if msg.value > 0 else 0x00
                if rtype == "FOOTSWITCH" and name in FOOTSWITCH_LOOKUP:
                    val = FOOTSWITCH_LOOKUP[name]
                    data = (
                        sysex_footswitch_ext(val, status)
                        if val > 0x7F
                        else sysex_footswitch_std(val, status)
                    )
                    send_sysex_to_ketron(_ketron_outport, data)
                    if verbose:
                        print(
                            f"[LAUNCHKEY-DAW-FILTER] CC {msg.control} -> FOOTSWITCH {name}"
                        )
                elif rtype == "TABS" and name in TABS_LOOKUP:
                    val = TABS_LOOKUP[name]
                    data = sysex_tabs(val, status)
                    send_sysex_to_ketron(_ketron_outport, data)
                    if verbose:
                        print(
                            f"[LAUNCHKEY-DAW-FILTER] CC {msg.control} -> TABS {name}"
                        )
            elif rtype == "CC" and "newval" in rule:
                _ketron_outport.send(msg)
                dup_msg = msg.copy(control=rule["newval"])
                _ketron_outport.send(dup_msg)
                if verbose:
                    print(
                        f"[LAUNCHKEY-DAW-FILTER] CC duplicato {msg.control}->{rule['newval']}"
                    )
        elif verbose:
            print(
                f"[LAUNCHKEY-DAW-FILTER] Nessuna regola per CC {msg.control} canale {msg.channel}"
            )
    else:
        if verbose:
            print(f"[LAUNCHKEY-DAW-FILTER] Messaggio ignorato: {msg}")

