import json
import logging

import mido

from tabs_lookup import TABS_LOOKUP
from footswitch_lookup import FOOTSWITCH_LOOKUP
from custom_sysex_lookup import CUSTOM_SYSEX_LOOKUP
from nrpn_lookup import resolve_nrpn_value
from sysex_utils import (
    send_sysex_to_ketron,
    sysex_tabs,
    sysex_footswitch_std,
    sysex_footswitch_ext,
    sysex_custom,
)
from paths import get_config_path

logger = logging.getLogger(__name__)

json_path = get_config_path("keypad_config.json")

try:
    with open(json_path) as f:
        KEYPAD_CONFIG = json.load(f)
except Exception:
    logger.exception(
        "Impossibile caricare la configurazione del keypad '%s'", json_path
    )
    KEYPAD_CONFIG = {}

DEFAULT_NRPN_CHANNEL = 15  # zero-based, corresponds to MIDI channel 16


def _resolve_nrpn_channel(mapping):
    """Return the MIDI channel for an NRPN mapping.

    Channel values must be expressed in common one-based (1-16) form used
    by most MIDI interfaces.  The optional ``channel``/``ch`` keys allow
    overriding the default channel defined by :data:`DEFAULT_NRPN_CHANNEL`.
    """

    raw_channel = mapping.get("channel")
    if raw_channel is None:
        raw_channel = mapping.get("ch")

    if raw_channel is None:
        return DEFAULT_NRPN_CHANNEL

    if isinstance(raw_channel, int):
        if 1 <= raw_channel <= 16:
            return raw_channel - 1

    return DEFAULT_NRPN_CHANNEL


def keypad_midi_callback(keycode, is_down, ketron_outport, verbose=False):
    mapping = KEYPAD_CONFIG.get(keycode)
    if not mapping:
        if verbose:
            logger.debug("Tasto %s non mappato", keycode)
        return

    cmd_type = mapping["type"]
    name = mapping["name"]
    sysex_bytes = None
    nrpn_sequence = None
    nrpn_channel = DEFAULT_NRPN_CHANNEL

    # Risolvi il comando e la stringa Sysex
    if cmd_type == "FOOTSWITCH":
        value = FOOTSWITCH_LOOKUP.get(name)
        if value is None:
            if verbose:
                logger.debug("FOOTSWITCH '%s' non trovato", name)
            return
        status = 0x7F if is_down else 0x00
        if value > 0x7F:
            sysex_bytes = sysex_footswitch_ext(value, status)
        else:
            sysex_bytes = sysex_footswitch_std(value, status)

    elif cmd_type == "TABS":
        value = TABS_LOOKUP.get(name)
        if value is None:
            if verbose:
                logger.debug("TABS '%s' non trovato", name)
            return
        status = 0x7F if is_down else 0x00
        sysex_bytes = sysex_tabs(value, status)

    elif cmd_type == "CUSTOM":
        custom = CUSTOM_SYSEX_LOOKUP.get(name)
        if not custom:
            if verbose:
                logger.debug("Custom Sysex '%s' non trovato", name)
            return
        param = custom["switch_map"]["toggle"] if is_down else custom["switch_map"]["off"]
        sysex_bytes = sysex_custom(custom["format"], param)

    elif cmd_type == "NRPN":
        if not is_down:
            if verbose:
                logger.debug("Rilascio NRPN '%s' ignorato", name)
            return

        value_key = mapping.get("value")
        if value_key is None:
            if verbose:
                logger.debug("NRPN '%s' senza valore associato", name)
            return

        resolved = resolve_nrpn_value(name, value_key)
        if not resolved:
            if verbose:
                logger.debug("NRPN '%s' valore '%s' non trovato", name, value_key)
            return

        msb, lsb, data_value = resolved
        nrpn_channel = _resolve_nrpn_channel(mapping)
        nrpn_sequence = [
            (0x63, msb),  # NRPN MSB
            (0x62, lsb),  # NRPN LSB
            (0x06, data_value),  # Data Entry MSB
        ]

    else:
        if verbose:
            logger.debug("Tipo comando '%s' non gestito", cmd_type)
        return

    # Stampa verbose
    if verbose:
        if sysex_bytes is not None:
            logger.debug(
                "Tasto %s: tipo=%s, comando='%s', sysex=%s",
                keycode,
                cmd_type,
                name,
                sysex_bytes,
            )
        elif nrpn_sequence is not None:
            logger.debug(
                "Tasto %s: tipo=%s, comando='%s', nrpn_channel=%s, sequence=%s",
                keycode,
                cmd_type,
                name,
                nrpn_channel,
                nrpn_sequence,
            )

    # Invia il sysex (solo se tutto è corretto)
    if sysex_bytes:
        send_sysex_to_ketron(ketron_outport, sysex_bytes)
    elif nrpn_sequence:
        for control, value in nrpn_sequence:
            msg = mido.Message(
                "control_change",
                channel=nrpn_channel,
                control=control,
                value=value,
            )
            ketron_outport.send(msg)
