"""Utilities for detecting and tracking graphical user sessions."""

from __future__ import annotations

import dataclasses
import os
import pwd
import subprocess
from typing import Dict, Optional


@dataclasses.dataclass(frozen=True)
class GraphicalSession:
    """Representation of a local graphical login session."""

    session_id: str
    username: str
    uid: int
    gid: int
    display: str
    xdg_runtime_dir: str
    home: str
    xauthority: str


def _session_properties(session_id: str) -> Dict[str, str]:
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


def find_active_graphical_session() -> Optional[GraphicalSession]:
    """Return information about the first active local graphical session."""

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
        props = _session_properties(session_id)
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

        xauthority = ""
        candidate_paths = []
        if runtime_dir:
            candidate_paths.append(os.path.join(runtime_dir, "gdm/Xauthority"))
        candidate_paths.append(os.path.join(pw_record.pw_dir, ".Xauthority"))

        for candidate in candidate_paths:
            if candidate and os.path.isfile(candidate):
                xauthority = candidate
                break

        return GraphicalSession(
            session_id=session_id,
            username=username,
            uid=pw_record.pw_uid,
            gid=pw_record.pw_gid,
            display=display,
            xdg_runtime_dir=runtime_dir,
            home=pw_record.pw_dir,
            xauthority=xauthority,
        )

    return None


def build_session_environment(
    session: Optional[GraphicalSession], base_env: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Compose an environment dictionary suitable for the graphical session."""

    env: Dict[str, str] = dict(base_env or {})
    if not session:
        return env

    if session.display:
        env["DISPLAY"] = session.display
    if session.xdg_runtime_dir:
        env["XDG_RUNTIME_DIR"] = session.xdg_runtime_dir
        env["DBUS_SESSION_BUS_ADDRESS"] = (
            f"unix:path={session.xdg_runtime_dir}/bus"
        )
    else:
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)

    env["HOME"] = session.home
    env["LOGNAME"] = session.username
    env["USER"] = session.username

    if session.xauthority:
        env["XAUTHORITY"] = session.xauthority

    return env
