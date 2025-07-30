# sysex_utils.py

import mido

def send_sysex_to_ketron(outport, data_bytes):
    """Invia un messaggio Sysex al Ketron tramite la porta MIDI aperta."""
    msg = mido.Message("sysex", data=data_bytes)
    outport.send(msg)

def sysex_tabs(tab_value, status):
    """
    Costruisce un sysex TABS.
    status: 0x00 (off) o 0x7F (on)
    """
    return [0x26, 0x7C, tab_value, status]

def sysex_footswitch_std(footswitch, status):
    """
    Costruisce un sysex FOOTSWITCH standard.
    status: 0x00 (released) o 0x7F (pressed)
    """
    return [0x26, 0x79, 0x03, footswitch, status]

def sysex_footswitch_ext(footswitch_value, status):
    """
    Costruisce un sysex FOOTSWITCH esteso (valori 0...16383).
    """
    fs1 = (footswitch_value >> 7) & 0x7F
    fs2 = footswitch_value & 0x7F
    return [0x26, 0x79, 0x05, fs1, fs2, status]

def sysex_custom(format_list, param_value):
    """
    Costruisce un sysex personalizzato sostituendo la parola chiave 'switch' con il valore effettivo.
    Esempio:
      format_list = [0x26, 0x7B, 0x25, 0x05, 'switch']
      param_value = 0x7F
      return [0x26, 0x7B, 0x25, 0x05, 0x7F]
    """
    return [b if b != "switch" else param_value for b in format_list]
