"""Background helper that mirrors the legacy start-touchdesk.sh script."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Dict, Optional

from configuration import WifiConfig
from session_utils import GraphicalSession, build_session_environment, find_active_graphical_session


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

    def _launch_vnc_for_session(self, session: GraphicalSession) -> None:
        def demote() -> None:
            if os.getuid() != 0:
                return
            try:
                os.initgroups(session.username, session.gid)
            except Exception as exc:
                self.logger.warning(
                    "Impossibile impostare i gruppi supplementari per '%s': %s",
                    session.username,
                    exc,
                )
            try:
                os.setgid(session.gid)
                os.setuid(session.uid)
            except OSError as exc:
                self.logger.warning(
                    "Impossibile cambiare utente in '%s' (uid=%s) per il client VNC: %s",
                    session.username,
                    session.uid,
                    exc,
                )

        env = self._build_env(session)

        subprocess.Popen(
            self.config.vnc_command,
            shell=True,
            env=env,
            preexec_fn=demote,
        )

    def _build_env(self, session: Optional[GraphicalSession]) -> Dict[str, str]:
        env = os.environ.copy()
        env = build_session_environment(session, base_env=env)
        return env

    def run(self) -> None:  # pragma: no cover - involves system interfaces
        if not self.config.enabled:
            return

        self.logger.info(
            "Monitoraggio Wi-Fi avviato per SSID '%s' al fine di lanciare il client VNC.",
            self.config.ssid,
        )

        launched_session: Optional[str] = None

        logged_waiting_session = False

        while not self.stop_event.is_set():
            ssid = self._current_ssid()
            if ssid == self.config.ssid:
                session = find_active_graphical_session()
                if not session:
                    if not logged_waiting_session:
                        self.logger.info(
                            "SSID '%s' rilevato ma nessuna sessione grafica attiva: "
                            "il comando VNC resterà in attesa.",
                            ssid,
                        )
                        logged_waiting_session = True
                    launched_session = None
                elif session.session_id != launched_session:
                    logged_waiting_session = False
                    self.logger.info(
                        "SSID '%s' rilevato: avvio del comando VNC come utente '%s'.",
                        ssid,
                        session.username,
                    )
                    try:
                        self._launch_vnc_for_session(session)
                        launched_session = session.session_id
                    except Exception:
                        self.logger.exception(
                            "Impossibile avviare il client VNC configurato"
                        )
                # Se la sessione è la stessa già gestita non fare nulla
            else:
                launched_session = None
                logged_waiting_session = False

            self.stop_event.wait(max(1, self.config.poll_interval))

    def stop(self) -> None:
        self.stop_event.set()
        if self.is_alive():
            self.join(timeout=5)
