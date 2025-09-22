"""Helpers for loading and representing the Armonix configuration."""

from __future__ import annotations

import configparser
import dataclasses
from dataclasses import dataclass
from typing import Optional

from paths import get_config_path, get_default_config_path


def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: str, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class WifiConfig:
    ssid: str = ""
    vnc_command: str = ""
    poll_interval: int = 5

    @property
    def enabled(self) -> bool:
        return bool(self.ssid and self.vnc_command)


@dataclass(frozen=True)
class MidiConfig:
    master_port_keyword: Optional[str] = None
    ketron_port_keyword: str = "MIDI Gadget"
    bluetooth_port_keyword: str = "Bluetooth"


@dataclass(frozen=True)
class ArmonixConfig:
    master: str = "fantom"
    headless: bool = True
    verbose: bool = False
    disable_realtime_display: bool = False
    keypad_device: str = (
        "/dev/input/by-id/usb-1189_USB_Composite_Device_CD70134330363235-if01-event-kbd"
    )
    midi: MidiConfig = dataclasses.field(default_factory=MidiConfig)
    wifi: WifiConfig = dataclasses.field(default_factory=WifiConfig)
    source_path: str = get_default_config_path("armonix.conf")


def load_config(path: Optional[str] = None) -> ArmonixConfig:
    parser = configparser.ConfigParser()

    config_path = get_config_path("armonix.conf") if path is None else path

    read_files = parser.read(config_path)
    if read_files:
        source_path = read_files[0]
    else:
        source_path = config_path

    master = parser.get("armonix", "master", fallback="fantom").strip().lower() or "fantom"
    headless = _as_bool(parser.get("armonix", "headless", fallback="true"), True)
    verbose = _as_bool(parser.get("armonix", "verbose", fallback="false"), False)
    disable_display = _as_bool(
        parser.get("armonix", "disable_realtime_display", fallback="false"), False
    )

    keypad_device = parser.get(
        "keypad", "device_path", fallback=ArmonixConfig().keypad_device
    ).strip()

    master_keyword = parser.get("midi", "master_port_keyword", fallback="").strip() or None
    ketron_keyword = parser.get("midi", "ketron_port_keyword", fallback="MIDI Gadget").strip()
    bluetooth_keyword = (
        parser.get("midi", "bluetooth_port_keyword", fallback="Bluetooth").strip()
    )

    wifi_ssid = parser.get("wifi", "ssid", fallback="").strip()
    wifi_cmd = parser.get("wifi", "vnc_command", fallback="").strip()
    wifi_interval = _as_int(parser.get("wifi", "poll_interval", fallback="5"), 5)
    midi_cfg = MidiConfig(
        master_port_keyword=master_keyword,
        ketron_port_keyword=ketron_keyword,
        bluetooth_port_keyword=bluetooth_keyword,
    )

    wifi_cfg = WifiConfig(
        ssid=wifi_ssid,
        vnc_command=wifi_cmd,
        poll_interval=wifi_interval,
    )

    return ArmonixConfig(
        master=master,
        headless=headless,
        verbose=verbose,
        disable_realtime_display=disable_display,
        keypad_device=keypad_device,
        midi=midi_cfg,
        wifi=wifi_cfg,
        source_path=source_path,
    )
