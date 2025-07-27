# custom_sysex_lookup.py
# Lookup e struttura per Sysex personalizzati (non TABS/FOOTSWITCH standard)

CUSTOM_SYSEX_LOOKUP = {
    # Esempio: MICRO 1 ECHO SWITCH ON/OFF
    "MICRO 1 ECHO SWITCH": {
        # La sequenza "format" include la parola chiave "switch" che verrà sostituita con il valore giusto
        "format": [0x26, 0x7B, 0x25, 0x05, "switch"],
        "switch_map": {
            "toggle": 0x7F,  # tipico per on/off toggle
            "off": 0x00,
            "on": 0x01
        }
    }
    # Puoi aggiungere qui altri custom, ad esempio:
    # "MY CUSTOM ACTION": {
    #     "format": [0x26, 0x7B, 0x12, "val1", "val2"],
    #     "param_map": {
    #         "up": 0x01,
    #         "down": 0x02
    #     }
    # }
}