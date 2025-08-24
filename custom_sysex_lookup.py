# custom_sysex_lookup.py
# Lookup e struttura per Sysex personalizzati (non TABS/FOOTSWITCH standard)

CUSTOM_SYSEX_LOOKUP = {
    "MICRO 1 SWITCH": {
        "format": [0x26, 0x7B, 0x1D, 0x05, "switch"],
        "switch_map": {
            "toggle": 0x7F,
            "off": 0x00,
            "on": 0x01
        }
    },
    "MICRO 1 TALK SWITCH": {
        "format": [0x26, 0x7B, 0x21, 0x05, "switch"],
        "switch_map": {
            "toggle": 0x7F,
            "off": 0x00,
            "on": 0x01
        }
    },
    "MICRO 1 ECHO SWITCH": {
        "format": [0x26, 0x7B, 0x25, 0x05, "switch"],
        "switch_map": {
            "toggle": 0x7F,  # tipico per on/off toggle
            "off": 0x00,
            "on": 0x01
        }
    },
    "VOICETRON ON/OFF": {
        "format": [0x26, 0x7B, 0x36, 0x00, "switch"],
        "switch_map": {
            "off": 0x7f,
            "on": 0x00
        }
    },
    "VOICETRON SWITCH": {
        "format": [0x26, 0x7B, 0x1E, 0x05, "switch"],
        "switch_map": {
            "toggle": 0x7F,  # tipico per on/off toggle
            "off": 0x00,
            "on": 0x01
        }
    },
    "ARRA_A_BREAK": {
        "levels": [
            {
                "name": "ARRA_A_BREAK",
                "min": 100,
                "max": 127,
                "color": 23,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x03, 0x7F],
                    [0x26, 0x79, 0x03, 0x16, 0x7F],
                    [0x26, 0x79, 0x03, 0x16, 0x00],
                ],
            },
            {
                "name": "NOTE_A",
                "min": 1,
                "max": 99,
                "color": 5,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x03, 0x7F],
                ],
            },
            {
                "name": "NOTE_A",
                "min": 0,
                "max": 0,
                "color": 0,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x03, 0x00],
                ],
            },
        ],
    },
}
