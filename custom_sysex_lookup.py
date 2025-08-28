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
    "ARR.A-BREAK": {
        "levels": [
            {
                "name": "ARRA_A_BREAK",
                "min": 110,
                "max": 127,
                "color": 55,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x16, 0x7F],
                    [0x26, 0x79, 0x03, 0x16, 0x00],
                    [0x26, 0x79, 0x03, 0x03, 0x7F],
                ],
            },
            {
                "min": 1,
                "max": 109,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x03, 0x7F],
                ],
            },
            {
                "min": 0,
                "max": 0,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x03, 0x00],
                ],
            },
        ],
    },
    "ARR.B-BREAK": {
        "levels": [
            {
                "name": "ARRA_A_BREAK",
                "min": 110,
                "max": 127,
                "color": 55,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x16, 0x7F],
                    [0x26, 0x79, 0x03, 0x16, 0x00],
                    [0x26, 0x79, 0x03, 0x04, 0x7F],
                ],
            },
            {
                "min": 1,
                "max": 109,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x04, 0x7F],
                ],
            },
            {
                "min": 0,
                "max": 0,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x04, 0x00],
                ],
            },
        ],
    },
    "ARR.C-BREAK": {
        "levels": [
            {
                "name": "ARRA_A_BREAK",
                "min": 110,
                "max": 127,
                "color": 55,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x16, 0x7F],
                    [0x26, 0x79, 0x03, 0x16, 0x00],
                    [0x26, 0x79, 0x03, 0x05, 0x7F],
                ],
            },
            {
                "min": 1,
                "max": 109,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x05, 0x7F],
                ],
            },
            {
                "min": 0,
                "max": 0,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x05, 0x00],
                ],
            },
        ],
    },
    "ARR.D-BREAK": {
        "levels": [
            {
                "name": "ARRA_A_BREAK",
                "min": 110,
                "max": 127,
                "color": 55,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x16, 0x7F],
                    [0x26, 0x79, 0x03, 0x16, 0x00],
                    [0x26, 0x79, 0x03, 0x06, 0x7F],
                ],
            },
            {
                "min": 1,
                "max": 109,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x06, 0x7F],
                ],
            },
            {
                "min": 0,
                "max": 0,
                "sysex": [
                    [0x26, 0x79, 0x03, 0x06, 0x00],
                ],
            },
        ],
    },
}
