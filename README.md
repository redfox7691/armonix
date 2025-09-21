# Armonix

Armonix is a compact MIDI control system designed to drive a Ketron EVM
using a MIDI keyboard and a small USB keypad.  Drivers are currently
available for the Roland Fantom 07 and the Novation Launchkey 88 [MK3].
The project has been tested on Linux Mint 21/24 but can be adapted to
other environments with minimal effort.

## Recommended hardware

* **Ketron EVM**
* **Roland Fantom 07** (also works with models 06 and 08)
* **Novation Launchkey [MK3]** (tested with the 88 key model)
* USB keypad with 12 keys and 2 encoders
* Linux laptop with touchscreen and VNC server for the Ketron console
* iPad connected via **MIDI over BLE** to display sheet music

## Installation

1. Install Python 3 and create a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install the main dependencies:

   ```bash
   pip install mido python-rtmidi evdev
   # Facoltativo per la barra LED grafica:
   pip install PyQt5
   ```

## Running

The main program is `main.py` which also shows a small status LED bar.
Run it with:

```bash
python main.py --verbose
```

To run Armonix on a machine without a display (and without installing
PyQt5) use the headless option:

```bash
python main.py --headless
```

Two helper scripts are included:

* `start_immortal.sh` runs `main.py` in a loop and automatically restarts
  the program if it exits.
* `start-touchdesk.sh` tries to connect to the Ketron EVM via VNC when
  the expected network is detected.

## Manual tests

To verify the Launchkey message filter you can run the manual script:

```bash
python tests/manual_launchkey_filter.py
```

The script confirms that only messages on channel 1 (mido channel 0) are
forwarded to the Ketron while others are discarded.

## Keypad configuration

`keypad_config.json` defines the mapping between keypad keys and Sysex,
Footswitch or NRPN messages sent to the Ketron.  Modify this file to
adapt the commands to your needs.

### NRPN commands

NRPN presets for the Ketron microphone section are listed in
`nrpn_lookup.py`.  Each entry exposes the NRPN MSB/LSB address and the
available values.  To trigger one of these presets from the keypad add a
mapping with `"type": "NRPN"` and specify the target preset with the
`value` field:

```json
"KEY_U": { "type": "NRPN", "name": "MICRO_PRESET", "value": "Standard" }
```

When the configured key is pressed the keypad sends the appropriate
Control Change sequence (`CC 99`, `CC 98`, `CC 06`) on MIDI channel 16.
The `value` field accepts both the human readable name and a raw integer
between 0 and 127, allowing custom presets to be added without modifying
the lookup table.

## Custom pads with velocity levels

Pads on the Launchkey can send different Sysex messages depending on the
received **velocity**.  In `custom_sysex_lookup.py` several levels can be
defined through the `levels` key, each specifying:

* velocity range (`min`/`max`)
* displayed name
* optional pad colour
* list of Sysex messages to send

Example:

```python
"ARRA_A_BREAK": {
    "levels": [
        {
            "name": "ARRA_A_BREAK",
            "min": 100,
            "max": 127,
            "color": 23,
            "sysex": [ [0x26, 0x79, 0x03, 0x03, 0x7F] ]
        },
        {
            "name": "NOTE_A",
            "min": 1,
            "max": 99,
            "color": 5,
            "sysex": [ [0x26, 0x79, 0x03, 0x03, 0x7F] ]
        }
    ]
}
```

In `launchkey_config.json` the pad can then be mapped with
`"type": "CUSTOM"` and the corresponding `name`:

```json
{ "note": 112, "channel": 0, "type": "CUSTOM", "name": "ARRA_A_BREAK", "group": 1, "color": 23, "colormode": "static" }
```

If a level defines a colour it overrides the standard one; otherwise the
behaviour defined by the group or configuration is used.

## Adapting to other setups

The logic is split into modules (state management, MIDI filters, keypad
listener) which makes it easy to extend the system to other instruments
or controllers.  You only need to adjust the mappings and, if required,
add new MIDI filter modules.

