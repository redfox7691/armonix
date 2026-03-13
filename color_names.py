"""Named colour constants for the Novation Launchkey MK3 colour palette.

The Launchkey MK3 accepts colour values 0-127.  This module maps
human-readable names to those values so that ``launchkey_config.json``
can be edited using plain words instead of raw numbers.

Reference: Launchkey MK3 Programmer's Reference Guide v1, p. 11.
"""

# ---------------------------------------------------------------------------
# Full palette mapping (name → velocity/value 0-127)
# ---------------------------------------------------------------------------
COLOR_NAMES: dict[str, int] = {
    # --- Neutrals ---
    "off":           0,
    "black":         0,
    "dark_grey":     1,
    "dark_gray":     1,
    "grey":          2,
    "gray":          2,
    "white":         3,

    # --- Row 1: reds / oranges ---
    "dim_red":       4,
    "red":           5,
    "orange_red":    6,
    "tomato":        6,
    "orange":        7,
    "yellow_orange": 8,
    "amber":         8,

    # --- Row 2: yellows / greens ---
    "yellow":        9,
    "lime":          10,
    "bright_lime":   11,
    "green":         12,
    "dark_green":    13,
    "forest":        13,

    # --- Row 3: cyans / blues ---
    "cyan":          14,
    "sky":           15,
    "sky_blue":      15,
    "blue":          16,
    "indigo":        17,
    "violet":        18,
    "purple":        18,

    # --- Row 4: pinks / magentas ---
    "magenta":       19,
    "hot_pink":      20,
    "fuchsia":       20,
    "pink":          21,
    "light_pink":    22,
    "rose":          23,

    # --- Row 5: dim/pastel hues (24-31) ---
    "dim_orange":    24,
    "dim_yellow":    25,
    "dim_lime":      26,
    "dim_green":     27,
    "dim_teal":      28,
    "dim_indigo":    29,
    "dim_violet":    30,
    "dim_pink":      31,

    # --- Row 6: medium-bright hues (32-39) ---
    "medium_red":    32,
    "medium_orange": 33,
    "medium_yellow": 34,
    "medium_green":  35,
    "teal":          36,
    "medium_blue":   37,
    "medium_violet": 38,
    "medium_pink":   39,

    # --- Row 7: muted/warm (40-47) ---
    "brown":         40,
    "dark_orange":   41,
    "sand":          42,
    "peach":         43,
    "cream":         44,
    "steel_blue":    45,
    "slate_blue":    46,
    "pale_grey":     47,

    # --- Row 8: cool pastels (48-55) ---
    "pale_red":      48,
    "salmon":        49,
    "pale_orange":   50,
    "pale_yellow":   51,
    "pale_green":    52,
    "pale_teal":     53,
    "pale_sky":      54,
    "pale_blue":     55,

    # --- Row 9: warm muted (56-63) ---
    "brick":         56,
    "maroon":        57,
    "dark_amber":    58,
    "olive":         59,
    "dark_lime":     60,
    "sea_green":     61,
    "dark_cyan":     62,
    "dark_blue":     63,

    # --- Right block, row 1: bright yellows (64-71) ---
    "bright_yellow": 64,
    "lemon":         65,
    "chartreuse":    66,
    "yellow_green":  67,
    "spring":        68,
    "mint":          69,
    "aquamarine":    70,
    "pale_mint":     71,

    # --- Right block, row 2: warm brights (72-79) ---
    "warm_yellow":   72,
    "gold":          73,
    "bright_orange": 74,
    "coral":         75,
    "crimson":       76,
    "deep_red":      77,
    "burgundy":      78,
    "dim_burgundy":  79,

    # --- Right block, row 3: pinks / purples (80-87) ---
    "blush":         80,
    "bright_pink":   81,
    "neon_pink":     82,
    "deep_magenta":  83,
    "deep_violet":   84,
    "deep_purple":   85,
    "dark_violet":   86,
    "dark_indigo":   87,

    # --- Right block, row 4: blues / teals (88-95) ---
    "aqua":          88,
    "bright_cyan":   89,
    "cornflower":    90,
    "light_blue":    91,
    "royal_blue":    92,
    "cobalt":        93,
    "periwinkle":    94,
    "lavender":      95,

    # --- Right block, row 5: light / pastel (96-103) ---
    "bright_white":  96,
    "pale_lemon":    97,
    "pale_chartreuse": 98,
    "pale_spring":   99,
    "ice_blue":      100,
    "powder_blue":   101,
    "lilac":         102,
    "pale_rose":     103,

    # --- Right block, row 6: softer pastels (104-111) ---
    "soft_yellow":   104,
    "soft_orange":   105,
    "soft_red":      106,
    "soft_pink":     107,
    "soft_violet":   108,
    "soft_blue":     109,
    "soft_teal":     110,
    "soft_green":    111,

    # --- Right block, row 7: very dim (112-119) ---
    "dim_warm":      112,
    "dim_coral":     113,
    "dim_rust":      114,
    "dim_rose2":     115,
    "dim_mauve":     116,
    "dim_slate":     117,
    "dim_sea":       118,
    "dim_sage":      119,

    # --- Right block, row 8: near-off (120-127) ---
    "near_off":      120,
    "faint_yellow":  121,
    "faint_green":   122,
    "faint_teal":    123,
    "faint_blue":    124,
    "faint_violet":  125,
    "faint_red":     126,
    "faint_pink":    127,
}

# Reverse map (value → canonical name) – keeps only the first name per value
VALUE_TO_NAME: dict[int, str] = {}
for _name, _val in COLOR_NAMES.items():
    if _val not in VALUE_TO_NAME:
        VALUE_TO_NAME[_val] = _name


def resolve_color(value: "int | str | None") -> int:
    """Return the numeric colour value (0-127) for *value*.

    *value* may be:
    - an ``int`` (returned as-is, clamped to 0-127)
    - a ``str`` colour name (looked up in :data:`COLOR_NAMES`)
    - ``None`` → returns 0 (off)

    Unknown names resolve to 0 (off) and a ``ValueError`` is raised so
    callers can decide whether to log a warning.
    """
    if value is None:
        return 0
    if isinstance(value, int):
        return max(0, min(value, 127))
    if isinstance(value, str):
        key = value.strip().lower()
        if key in COLOR_NAMES:
            return COLOR_NAMES[key]
        # Try as a plain integer string ("5", "0x0A", …)
        try:
            return max(0, min(int(key, 0), 127))
        except (ValueError, TypeError):
            pass
        raise ValueError(f"Unknown Launchkey colour name: {value!r}")
    raise TypeError(f"Colour must be int, str or None, got {type(value).__name__!r}")
