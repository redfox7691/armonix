"""Background helper that mirrors the legacy start-touchdesk.sh script."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Dict, Optional

from configuration import WifiConfig


class WifiVncLauncher(threading.Thread):
    """Monitor the current Wi-Fi SSID and launch a VNC client when needed."""

    def __init__(
        self,
        wifi_config: WifiConfig,
        stop_event: Optional[threading.Event] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.config = wifi_config
        self.stop_event = stop_event or threading.Event()
        self.logger = logger or logging.getLogger(__name__)

    def _current_ssid(self) -> str:
        try:
            output = subprocess.check_output(["iwgetid", "-r"], text=True).strip()
            return output
        except Exception:
            return ""

    def _build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        if self.config.display:
            env["DISPLAY"] = self.config.display
        if self.config.xdg_runtime_dir:
            env["XDG_RUNTIME_DIR"] = self.config.xdg_runtime_dir
        if self.config.dbus_session_address:
            env["DBUS_SESSION_BUS_ADDRESS"] = self.config.dbus_session_address
        return env

    def run(self) -> None:  # pragma: no cover - involves system interfaces
        if not self.config.enabled:
            return

        self.logger.info(
            "Monitoraggio Wi-Fi avviato per SSID '%s' al fine di lanciare il client VNC.",
            self.config.ssid,
        )

        while not self.stop_event.is_set():
            ssid = self._current_ssid()
            if ssid == self.config.ssid:
                self.logger.info(
                    "SSID '%s' rilevato: avvio del comando VNC configurato.", ssid
                )
                try:
                    subprocess.Popen(
                        self.config.vnc_command,
                        shell=True,
                        env=self._build_env(),
                    )
                except Exception:
                    self.logger.exception("Impossibile avviare il client VNC configurato")
                return

            time.sleep(max(1, self.config.poll_interval))

    def stop(self) -> None:
        self.stop_event.set()
