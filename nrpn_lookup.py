"""Lookup tables for NRPN commands handled by the keypad controller.

Each entry defines the NRPN address (MSB/LSB) and the available values.
The values dictionary maps human readable names to the integer value that
must be sent as Data Entry MSB (Control Change 06h).
"""

NRPN_LOOKUP = {
    "MICRO_PRESET": {
        "msb": 0x70,
        "lsb": 0x21,
        "values": {
            "Standard": 0x00,
            "Mellow": 0x01,
            "Small": 0x02,
            "Large": 0x03,
            "Gated": 0x04,
            "Live": 0x05,
            "Solo Echo": 0x06,
            "Special Efx1": 0x07,
            "Special Efx2": 0x08,
            "Double Voice": 0x09,
            "User 01": 0x0A,
            "User 02": 0x0B,
            "User 03": 0x0C,
            "User 04": 0x0D,
            "User 05": 0x0E,
            "User 06": 0x0F,
            "User 07": 0x10,
            "User 08": 0x11,
            "User 09": 0x12,
            "User 10": 0x13,
        },
    },
    "MICRO_COMPRESSOR_PRESET": {
        "msb": 0x70,
        "lsb": 0x40,
        "values": {
            "OFF": 0x00,
            "compr -15dB 2:1": 0x01,
            "compr -18dB 3:1": 0x02,
            "compr -21dB 7:1": 0x03,
            "compr -18dB 2:1": 0x04,
            "compr -24dB 2:1": 0x05,
            "limiter -6dB": 0x06,
            "limiter -18dB": 0x07,
        },
    },
    "MICRO_EQ_PRESET": {
        "msb": 0x70,
        "lsb": 0x6B,
        "values": {
            "OFF": 0x00,
            "Male": 0x01,
            "Female": 0x02,
            "Robot": 0x03,
            "Duck": 0x04,
            "Bear": 0x05,
            "Mouse": 0x06,
            "Dark": 0x07,
            "Cartoon": 0x08,
            "Doubling Choir": 0x09,
        },
    },
    "MICRO_ECHO_PRESET": {
        "msb": 0x70,
        "lsb": 0x30,
        "values": {
            "Standard": 0x00,
            "Flat": 0x01,
            "Brilliance": 0x02,
            "Studio": 0x03,
            "User 01": 0x04,
            "User 02": 0x05,
            "User 03": 0x06,
            "User 04": 0x07,
        },
    },
}


def resolve_nrpn_value(name, value_key):
    """Return the NRPN address/value tuple for the requested preset.

    Parameters
    ----------
    name: str
        Identifier of the NRPN command, as defined in ``NRPN_LOOKUP``.
    value_key: str | int
        Human readable preset name or integer value.  When an integer is
        provided it is returned as-is, allowing advanced users to bypass
        the lookup table.

    Returns
    -------
    tuple[int, int, int] | None
        A tuple ``(msb, lsb, value)`` or ``None`` if the lookup fails.
    """

    entry = NRPN_LOOKUP.get(name)
    if not entry:
        return None

    if isinstance(value_key, int):
        if 0 <= value_key <= 0x7F:
            return entry["msb"], entry["lsb"], value_key
        return None

    if isinstance(value_key, str):
        value = entry["values"].get(value_key)
        if value is not None:
            return entry["msb"], entry["lsb"], value

    return None
