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
    """Load launchkey_config.json stripping comments.

    Besides the regular NOTE/CC mappings this loader also initializes
    ``LAUNCHKEY_GROUPS`` which describes selector groups.  Each group is a
    dictionary with ``on_color`` and ``off_color`` along with the list of
    member controls.
    """

    filters = {"NOTE": {}, "CC": {}}
    groups = {}
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

    for grp in data.get("SELECTOR_GROUPS", []):
        gid = grp.get("group_id")
        if gid is None:
            continue
        groups[int(gid)] = {
            "on_color": grp.get("on_color"),
            "off_color": grp.get("off_color"),
            "members": [],
        }

    for entry in data.get("NOTE", []):
        chan = entry.get("channel")
        note = entry.get("note")
        if chan is None or note is None:
            continue
        filters["NOTE"].setdefault(chan, {})[note] = entry
        gid = entry.get("group")
        if gid is not None:
            groups.setdefault(int(gid), {"on_color": None, "off_color": None, "members": []})[
                "members"
            ].append(("NOTE", int(note)))

    for entry in data.get("CC", []):
        chan = entry.get("channel")
        cc = entry.get("control")
        if chan is None or cc is None:
            continue
        filters["CC"].setdefault(chan, {})[cc] = entry
        gid = entry.get("group")
        if gid is not None:
            groups.setdefault(int(gid), {"on_color": None, "off_color": None, "members": []})[
                "members"
            ].append(("CC", int(cc)))

    global LAUNCHKEY_GROUPS
    LAUNCHKEY_GROUPS = groups

    return filters


LAUNCHKEY_GROUPS = {}
LAUNCHKEY_FILTERS = _load_launchkey_filters(_config_path)


def _send_color(outport, section, pid, color, mode="static"):
    """Send a color update to the Launchkey for a pad or control."""

    if color is None:
        return

    mode_alias = {"static": "stationary"}
    mode_to_channel = {"stationary": 0, "flashing": 1, "pulsing": 2}
    colormode = mode_alias.get(mode, mode)
    chan = mode_to_channel.get(colormode, 0)
    val = max(0, min(int(color), 127))
    pid = int(pid) & 0x7F

    if section == "NOTE":
        msg = mido.Message("note_on", channel=chan, note=pid, velocity=val)
    else:
        msg = mido.Message("control_change", channel=chan, control=pid, value=val)
    outport.send(msg)


def _apply_group_colors(outport, section, pid, group_id, mode="static"):
    """Color helper for selector groups."""

    group = LAUNCHKEY_GROUPS.get(int(group_id))
    if not group:
        return

    on_color = group.get("on_color")
    off_color = group.get("off_color")

    _send_color(outport, section, pid, on_color, mode)

    for sec, member_pid in group.get("members", []):
        if sec == section and member_pid == pid:
            continue
        _send_color(outport, sec, member_pid, off_color, mode)


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

            if is_on:
                group_id = rule.get("group")
                if group_id is not None:
                    _apply_group_colors(
                        daw_outport,
                        "NOTE",
                        msg.note,
                        group_id,
                        rule.get("colormode", "static"),
                    )
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
                if msg.value > 0:
                    group_id = rule.get("group")
                    if group_id is not None:
                        _apply_group_colors(
                            daw_outport,
                            "CC",
                            msg.control,
                            group_id,
                            rule.get("colormode", "static"),
                        )
            elif rtype == "CC" and "newval" in rule:
                _ketron_outport.send(msg)
                dup_msg = msg.copy(control=rule["newval"], channel=0)
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

