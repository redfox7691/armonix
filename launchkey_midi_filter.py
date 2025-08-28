import json
import os
import re
import subprocess
import threading
from datetime import datetime

import mido

from footswitch_lookup import FOOTSWITCH_LOOKUP
from tabs_lookup import TABS_LOOKUP
from sysex_utils import (
    send_sysex_to_ketron,
    sysex_tabs,
    sysex_footswitch_std,
    sysex_footswitch_ext,
    sysex_custom,
)
from custom_sysex_lookup import CUSTOM_SYSEX_LOOKUP

MASTER_PORT_KEYWORD = "Launchkey MK3 88 LKMK3 MIDI In"
DAW_IN_PORT_KEYWORD = "Launchkey MK3 88 LKMK3 DAW In"
DAW_OUT_PORT_KEYWORD = "Launchkey MK3 88 LKMK3 DAW In"


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

CUSTOM_TOGGLE_STATES = {}

_display_timer = None
_default_lines = ("", "")

_daw_connected = False
_daw_in_port = None
_daw_out_port = None
_daw_listener_thread = None
_daw_listener_stop = None


def _send_display(outport, line1, line2, verbose=False):
    hdr = [0x00, 0x20, 0x29, 0x02, 0x12, 0x04]
    line1 = line1.ljust(16)[:16]
    line2 = line2.ljust(16)[:16]
    data = hdr + [0x00] + [ord(c) & 0x7F for c in line1]
    if verbose:
        print(f"[DAW] set display sysex {data}")
    outport.send(mido.Message("sysex", data=data))
    data = hdr + [0x01] + [ord(c) & 0x7F for c in line2]
    if verbose:
        print(f"[DAW] set display sysex {data}")
    outport.send(mido.Message("sysex", data=data))


def init_default_display(outport, verbose=False):
    """Compute default message with git info and show it."""
    global _default_lines
    try:
        version = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"], cwd=base_dir
        ).decode().strip()
    except Exception:
        version = "0"
    try:
        date = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=format:%d/%m/%Y"],
            cwd=base_dir,
        ).decode().strip()
    except Exception:
        date = datetime.now().strftime("%d/%m/%Y")
    line1 = "Armonix".center(16)
    line2 = f"{date} v{version}".center(16)
    _default_lines = (line1[:16], line2[:16])
    _send_display(outport, *_default_lines, verbose=verbose)


def show_default_display(outport, verbose=False):
    _send_display(outport, *_default_lines, verbose=verbose)


def show_temp_display(outport, line1, line2, verbose=False):
    global _display_timer
    if _display_timer:
        _display_timer.cancel()
    _send_display(outport, line1, line2, verbose=verbose)
    _display_timer = threading.Timer(3.0, show_default_display, args=(outport, verbose))
    _display_timer.start()


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


# --- DAW helper functions -------------------------------------------------

def poll_ports(state_manager):
    """Handle Launchkey-specific port detection and listeners."""
    global _daw_connected, _daw_in_port, _daw_out_port

    daw_in_port = state_manager.find_port(DAW_IN_PORT_KEYWORD)
    daw_out_port = state_manager.find_output_port(DAW_OUT_PORT_KEYWORD)

    if (
        state_manager.ketron_port
        and daw_in_port
        and daw_out_port
        and not _daw_connected
    ):
        _daw_in_port = daw_in_port
        _daw_out_port = daw_out_port
        _daw_connected = True
        if state_manager.verbose:
            print(f"Porta DAW collegata: in={daw_in_port}, out={daw_out_port}")
        start_daw_listener(state_manager)
    elif _daw_connected and (
        not state_manager.ketron_port or not daw_in_port or not daw_out_port
    ):
        if state_manager.verbose:
            print("Porta DAW scollegata")
        _daw_connected = False
        _daw_in_port = None
        _daw_out_port = None
        stop_daw_listener()


def start_daw_listener(state_manager):
    """Start listener thread for Launchkey DAW port."""
    global _daw_listener_thread, _daw_listener_stop
    if _daw_listener_thread and _daw_listener_thread.is_alive():
        return
    _daw_listener_stop = threading.Event()

    def daw_listener():
        if state_manager.verbose:
            print(
                f"[DAW-THREAD] Avvio thread: porta DAW in={_daw_in_port}, out={_daw_out_port}"
            )
        try:
            with mido.open_input(_daw_in_port) as inport, mido.open_output(
                _daw_out_port, exclusive=False
            ) as outport:
                init_msg = mido.Message("note_on", channel=15, note=0x0C, velocity=0x7F)
                outport.send(init_msg)
                if state_manager.verbose:
                    print(f"[DAW] Inviato init: {init_msg}")
                init_msg = mido.Message("note_off", channel=15, note=0x0D, velocity=0x7F)
                outport.send(init_msg)
                if state_manager.verbose:
                    print(f"[DAW] Inviato init: {init_msg}")
                init_msg = mido.Message("note_off", channel=15, note=0x0A, velocity=0x7F)
                outport.send(init_msg)
                if state_manager.verbose:
                    print(f"[DAW] Inviato init: {init_msg}")
                init_msg = mido.Message("note_on", channel=15, note=0x0C, velocity=0x7F)
                outport.send(init_msg)
                if state_manager.verbose:
                    print(f"[DAW] Inviato init: {init_msg}")

                init_default_display(outport, verbose=state_manager.verbose)
                CUSTOM_TOGGLE_STATES.clear()

                mode_to_channel = {"stationary": 0, "flashing": 1, "pulsing": 2}
                mode_alias = {"static": "stationary"}

                if state_manager.verbose:
                    print("[DAW] Invio i colori dei pulsanti se sono definiti")

                for section, ch_map in LAUNCHKEY_FILTERS.items():
                    for ch, id_map in ch_map.items():
                        for pid, meta in id_map.items():
                            color = meta.get("color")
                            if color is None:
                                color = meta.get("color_off")
                                if color is None:
                                    color = meta.get("color_on")
                            if color is not None:
                                raw_mode = meta.get("colormode", "stationary")
                                colormode = mode_alias.get(raw_mode, raw_mode)

                                note = int(pid) & 0x7F
                                vel = max(0, min(int(color), 127))
                                chan = mode_to_channel.get(colormode, 0)

                                if state_manager.verbose:
                                    print(
                                        f"[DAW] Colore {vel} {colormode} su pid {note} -> ch {chan}"
                                    )

                                if section == "NOTE":
                                    color_msg = mido.Message(
                                        "note_on", channel=chan, note=note, velocity=vel
                                    )
                                else:
                                    color_msg = mido.Message(
                                        "control_change", channel=chan, control=note, value=vel
                                    )
                                outport.send(color_msg)

                            lcd_idx = meta.get("lcd_index")
                            lcd_name = meta.get("name")
                            if lcd_idx is not None and lcd_name:
                                hdr = [0x00, 0x20, 0x29, 0x02, 0x12]
                                txt = str(lcd_name)[:16]
                                data = hdr + [0x07, int(lcd_idx) & 0x7F] + [ord(c) & 0x7F for c in txt]
                                if state_manager.verbose:
                                    print(f"[DAW] invio sysex {data}")
                                outport.send(mido.Message("sysex", data=data))

                if state_manager.verbose:
                    print("[DAW] In ascolto sulla porta DAW.")
                for msg in inport:
                    if _daw_listener_stop.is_set():
                        break
                    filter_and_translate_launchkey_daw_msg(
                        msg, outport, state_manager, verbose=state_manager.verbose
                    )
        except Exception as e:
            if state_manager.verbose:
                print(f"[DAW] Errore: {e}")

    _daw_listener_thread = threading.Thread(target=daw_listener, daemon=True)
    _daw_listener_thread.start()


def stop_daw_listener():
    """Stop the DAW listener thread."""
    global _daw_listener_thread, _daw_listener_stop, _ketron_outport
    if _daw_listener_stop:
        _daw_listener_stop.set()
    thread = _daw_listener_thread
    if thread:
        thread.join(timeout=1)
    _daw_listener_thread = None
    try:
        if _ketron_outport:
            _ketron_outport.close()
    except Exception:
        pass
    _ketron_outport = None

# --- Master port filter ---------------------------------------------------

def filter_and_translate_msg(
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
            if rtype == "CUSTOM" and name in CUSTOM_SYSEX_LOOKUP:
                custom = CUSTOM_SYSEX_LOOKUP[name]
                if "switch_map" in custom:
                    if is_on:
                        state = CUSTOM_TOGGLE_STATES.get(name, False)
                        action = "on" if not state else "off"
                        param = custom["switch_map"][action]
                        data = sysex_custom(custom["format"], param)
                        send_sysex_to_ketron(_ketron_outport, data)
                        color_key = "color_on" if action == "on" else "color_off"
                        _send_color(
                            daw_outport,
                            "NOTE",
                            msg.note,
                            rule.get(color_key),
                            rule.get("colormode", "static"),
                        )
                        CUSTOM_TOGGLE_STATES[name] = not state
                        if verbose:
                            print(
                                f"[LAUNCHKEY-DAW-FILTER] NOTE -> CUSTOM {name} {action.upper()}"
                            )
                        if not state_manager.disable_realtime_display:
                            show_temp_display(daw_outport, "CUSTOM", name, verbose)
                    return
                elif "levels" in custom:
                    velocity = msg.velocity if msg.type == "note_on" else 0
                    level = next(
                        (
                            lvl
                            for lvl in custom["levels"]
                            if lvl["min"] <= velocity <= lvl["max"]
                        ),
                        None,
                    )
                    if level:
                        for data in level["sysex"]:
                            send_sysex_to_ketron(_ketron_outport, data)
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
                        if "color" in level:
                            _send_color(
                                daw_outport,
                                "NOTE",
                                msg.note,
                                level["color"],
                                rule.get("colormode", "static"),
                            )
                        disp_name = level.get("name", name)
                        if verbose:
                            print(
                                f"[LAUNCHKEY-DAW-FILTER] NOTE -> CUSTOM {disp_name} (vel {velocity})"
                            )
                        if not state_manager.disable_realtime_display:
                            show_temp_display(daw_outport, "CUSTOM", disp_name, verbose)
                        return
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
                if is_on and not state_manager.disable_realtime_display:
                    show_temp_display(daw_outport, "FOOTSWITCH", name, verbose)
            elif rtype == "TABS" and name in TABS_LOOKUP:
                val = TABS_LOOKUP[name]
                data = sysex_tabs(val, status)
                send_sysex_to_ketron(_ketron_outport, data)
                if verbose:
                    print(f"[LAUNCHKEY-DAW-FILTER] NOTE -> TABS {name} {'ON' if is_on else 'OFF'}")
                if is_on and not state_manager.disable_realtime_display:
                    show_temp_display(daw_outport, "TABS", name, verbose)

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
            if rtype == "CUSTOM" and name in CUSTOM_SYSEX_LOOKUP:
                if msg.value > 0:
                    custom = CUSTOM_SYSEX_LOOKUP[name]
                    state = CUSTOM_TOGGLE_STATES.get(name, False)
                    action = "on" if not state else "off"
                    param = custom["switch_map"][action]
                    data = sysex_custom(custom["format"], param)
                    send_sysex_to_ketron(_ketron_outport, data)
                    color_key = "color_on" if action == "on" else "color_off"
                    _send_color(
                        daw_outport,
                        "CC",
                        msg.control,
                        rule.get(color_key),
                        rule.get("colormode", "static"),
                    )
                    CUSTOM_TOGGLE_STATES[name] = not state
                    if verbose:
                        print(
                            f"[LAUNCHKEY-DAW-FILTER] CC {msg.control} -> CUSTOM {name} {action.upper()}"
                        )
                    if not state_manager.disable_realtime_display:
                        show_temp_display(daw_outport, "CUSTOM", name, verbose)
                return
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
                    if msg.value > 0 and not state_manager.disable_realtime_display:
                        show_temp_display(daw_outport, "FOOTSWITCH", name, verbose)
                elif rtype == "TABS" and name in TABS_LOOKUP:
                    val = TABS_LOOKUP[name]
                    data = sysex_tabs(val, status)
                    send_sysex_to_ketron(_ketron_outport, data)
                    if verbose:
                        print(
                            f"[LAUNCHKEY-DAW-FILTER] CC {msg.control} -> TABS {name}"
                        )
                    if msg.value > 0 and not state_manager.disable_realtime_display:
                        show_temp_display(daw_outport, "TABS", name, verbose)
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

