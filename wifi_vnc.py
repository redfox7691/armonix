"""Background helper that mirrors the legacy start-touchdesk.sh script."""

from __future__ import annotations

import dataclasses
import logging
import os
import pwd
import subprocess
import threading
import time
from typing import Dict, Optional

from configuration import WifiConfig


@dataclasses.dataclass
class _GraphicalSession:
    username: str
    uid: int
    gid: int
    display: str
    xdg_runtime_dir: str
    home: str


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

    def _session_properties(self, session_id: str) -> Dict[str, str]:
        try:
            output = subprocess.check_output(
                [
                    "loginctl",
                    "show-session",
                    session_id,
                    "--property=Name",
                    "--property=User",
                    "--property=UID",
                    "--property=Type",
                    "--property=State",
                    "--property=Active",
                    "--property=Remote",
                    "--property=Display",
                ],
                text=True,
            )
        except Exception:
            return {}

        properties: Dict[str, str] = {}
        for line in output.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            properties[key] = value.strip()
        return properties

    def _active_graphical_session(self) -> Optional[_GraphicalSession]:
        try:
            sessions_output = subprocess.check_output(
                ["loginctl", "list-sessions", "--no-legend"], text=True
            )
        except Exception:
            return None

        for line in sessions_output.splitlines():
            parts = line.split()
            if not parts:
                continue
            session_id = parts[0]
            props = self._session_properties(session_id)
            if not props:
                continue
            session_type = props.get("Type", "").lower()
            if session_type not in {"x11", "wayland"}:
                continue
            if props.get("Remote", "no").lower() == "yes":
                continue
            is_active = props.get("Active", "no").lower() in {"yes", "1"}
            state_active = props.get("State", "").lower() == "active"
            if not (is_active or state_active):
                continue
            display = props.get("Display", "").strip()
            if not display:
                continue
            username = props.get("Name") or props.get("User")
            if not username:
                continue
            try:
                pw_record = pwd.getpwnam(username)
            except KeyError:
                continue
            runtime_dir = os.path.join("/run/user", str(pw_record.pw_uid))
            if not os.path.isdir(runtime_dir):
                runtime_dir = ""
            return _GraphicalSession(
                username=username,
                uid=pw_record.pw_uid,
                gid=pw_record.pw_gid,
                display=display,
                xdg_runtime_dir=runtime_dir,
                home=pw_record.pw_dir,
            )
        return None

    def _launch_vnc_for_session(self, session: _GraphicalSession) -> None:
        def demote() -> None:
            try:
                os.initgroups(session.username, session.gid)
            except Exception:
                pass
            os.setgid(session.gid)
            os.setuid(session.uid)

        env = self._build_env(session)
        env.setdefault("HOME", session.home)
        env.setdefault("LOGNAME", session.username)
        env.setdefault("USER", session.username)

        subprocess.Popen(
            self.config.vnc_command,
            shell=True,
            env=env,
            preexec_fn=demote,
        )

    def _build_env(self, session: Optional[_GraphicalSession]) -> Dict[str, str]:
        env = os.environ.copy()
        display = self.config.display or (session.display if session else "")
        if display:
            env["DISPLAY"] = display
        runtime_dir = self.config.xdg_runtime_dir or (
            session.xdg_runtime_dir if session else ""
        )
        if runtime_dir:
            env["XDG_RUNTIME_DIR"] = runtime_dir
            env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime_dir}/bus")
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
                session = self._active_graphical_session()
                if not session:
                    self.logger.info(
                        "SSID '%s' rilevato ma nessuna sessione grafica attiva: "
                        "il client VNC non verrà avviato.",
                        ssid,
                    )
                    return
                self.logger.info(
                    "SSID '%s' rilevato: avvio del comando VNC come utente '%s'.",
                    ssid,
                    session.username,
                )
                try:
                    self._launch_vnc_for_session(session)
                except Exception:
                    self.logger.exception("Impossibile avviare il client VNC configurato")
                return

            time.sleep(max(1, self.config.poll_interval))

    def stop(self) -> None:
        self.stop_event.set()
