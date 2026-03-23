# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Armonix** (v1.05) is a Python MIDI control system that bridges a master keyboard (Roland Fantom 07 or Novation Launchkey 88 MK3) and a USB keypad to drive a Ketron EVM electronic organ. It runs as a Linux daemon with an optional PyQt5 GUI.

## Commands

### Running (Development)
```bash
# Install dependencies (first time)
python3 -m venv venv && source venv/bin/activate
pip install mido python-rtmidi evdev PyQt5

# Run headless MIDI engine
python armonix_service.py --verbose

# Run with GUI
python armonix_gui_service.py --gui --verbose

# Key flags
--master [fantom|launchkey]
--config <path>
--disable_realtime_display / --enable_realtime_display
```

### Build (Debian package)
```bash
make deb   # Produces build/deb/armonix_1.03.deb
```

### Testing
```bash
python tests/manual_launchkey_filter.py
```
No automated test suite exists — manual testing with real hardware is the primary validation approach.

## Architecture

### Entry Points
- `armonix_service.py` — headless MIDI engine
- `armonix_gui_service.py` — GUI service (PyQt5 LED bar + VNC monitoring)

### Core Flow
1. **StateManager** (`statemanager.py`) polls MIDI ports every 1s via `mido.get_input_names()` using keyword matching
2. When both master keyboard and Ketron ports are detected → `ready` state; either missing → `waiting`
3. Separate daemon threads: `MasterListener`, `KeypadListener`, `BleListener`
4. Each MIDI message from master is passed through the active filter module, which transforms/routes it to the Ketron output port

### Pluggable Filter System
Master keyboard selection dynamically imports the filter module at runtime:
```python
master_module = importlib.import_module(f"{master}_midi_filter")
```
- `fantom_midi_filter.py` — velocity-coded instructions (1=footswitch std, 2=footswitch ext, 3=tabs), CC/NRPN handling; channel 0 forwarded unmodified
- `launchkey_midi_filter.py` — loads `launchkey_config.json` for note/CC/sysex mappings, LED color management, DAW mode, mouse IPC

Both implement `filter_and_translate_msg(msg, outport, state_manager, ...)`.

### Configuration
`configuration.py` uses dataclasses (`ArmonixConfig`, `MidiConfig`, `VncConfig`).

**All three config files** (`armonix.conf`, `keypad_config.json`, `launchkey_config.json`) are resolved via `get_config_path()` in `paths.py` using the same lookup order:

| Priority | Location | When used |
|----------|----------|-----------|
| 1 | `/etc/armonix/<file>` | System install (package) or manual override |
| 2 | `PACKAGE_DIR/<file>` | Fallback: directory where `paths.py` lives — `/usr/lib/armonix/` (installed) or the source tree (development) |
| 3 | `/etc/armonix/<file>` | Last resort even if not present |

In development the source tree itself acts as `PACKAGE_DIR`, so edited JSON files take effect immediately without copying anywhere.

Config file roles:
- `armonix.conf` — runtime flags (master keyboard, MIDI port keywords, VNC, keypad device path)
- `launchkey_config.json` — pad/note/CC mappings with `SELECTOR_GROUPS` for color coordination
- `keypad_config.json` — USB keypad scancode → MIDI action mappings (NRPN, FOOTSWITCH, TABS, CUSTOM types)

### IPC: Mouse Control
`mouse_ipc.py` provides a Unix socket server at `/tmp/armonix-mouse.sock`. The Launchkey filter sends JSON `{"action": "press|release", "x": int, "y": int}` to trigger `xdotool` mouse events. The socket is created by `armonix_gui_service.py` (requires display).

### LED States
StateManager maintains 5 LED states: `[Master, Ketron, Keypad, Bluetooth, SystemState]`. The PyQt5 `ledbar.py` widget displays these visually; animated in `waiting`, solid in `ready`/`paused`.

### Lookup Tables
Velocity/command-to-sysex mapping: `custom_sysex_lookup.py`, `footswitch_lookup.py`, `nrpn_lookup.py`, `tabs_lookup.py`. `sysex_utils.py` constructs raw SysEx byte sequences.

### Logging
Root logger `armonix`; outputs to syslog (`/dev/log`) or stderr. Child loggers: `armonix.statemanager`, `armonix.vnc`, `armonix.mouse`. `--verbose` enables DEBUG level + timestamps.

## Services (Systemd)
- `armonix.service` — system-wide, runs as `armonix` user, starts at boot
- `armonix-gui.service` — user service, starts after graphical login

## Key Development Notes (from CONTRIBUTING.md)
- Launchkey operates in **DAW mode** on startup (required for full LED control)
- LED colors are channel-dependent: channel 0 = static LED, channel 1 = flash, channel 2 = pulse
- `SELECTOR_GROUPS` in `launchkey_config.json` coordinate pad colors so only the selected pad is lit
- When adding new pad behaviors, use velocity ranges in `custom_sysex_lookup.py`
- SysEx for Launchkey LCD display uses manufacturer ID `0x00 0x20 0x29`
