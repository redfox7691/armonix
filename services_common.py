"""Common helpers shared by Armonix services. / Helper comuni per i servizi Armonix."""

from __future__ import annotations

import logging
import os
from logging.handlers import SysLogHandler
from typing import Optional

from statemanager import StateManager


class LoggerWriter:
    """Redirect ``print`` output to logging. / Reindirizza ``print`` verso il logging."""

    def __init__(self, level: int) -> None:
        self.level = level
        self.logger = logging.getLogger("armonix")

    def write(self, message: str) -> None:
        """Forward a message to the logger. / Inoltra un messaggio al logger."""

        if not message:
            return
        message = message.rstrip()
        if not message:
            return
        for line in message.splitlines():
            self.logger.log(self.level, line)

    def flush(self) -> None:  # pragma: no cover - API requirement
        """Flush placeholder for compatibility. / Svuota il buffer (se richiesto) per compatibilità."""


def configure_logging(verbose: bool) -> logging.Logger:
    """Prepare the root Armonix logger. / Prepara il logger principale di Armonix."""

    logger = logging.getLogger("armonix")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    formatter = logging.Formatter("armonix[%(process)d]: %(message)s")

    try:
        syslog_handler = SysLogHandler(address="/dev/log")
        syslog_handler.setFormatter(formatter)
        logger.addHandler(syslog_handler)
    except OSError:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if verbose:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(console)

    logger.propagate = False
    return logger


def setup_child_logger(name: str, parent: logging.Logger) -> logging.Logger:
    """Clone the parent's handlers for a child logger. / Duplica gli handler del logger padre."""

    child = logging.getLogger(name)
    child.propagate = False
    for handler in list(child.handlers):
        child.removeHandler(handler)
    for handler in parent.handlers:
        child.addHandler(handler)
    child.setLevel(parent.level)
    return child


def create_state_manager(
    *,
    verbose: bool,
    master: str,
    disable_realtime_display: bool,
    master_port_keyword: Optional[str],
    ketron_port_keyword: Optional[str],
    ble_port_keyword: Optional[str],
    keypad_device: Optional[str],
    enable_midi_io: bool,
    parent_logger: Optional[logging.Logger] = None,
) -> StateManager:
    """Instantiate :class:`StateManager`. / Crea un'istanza di :class:`StateManager`."""

    state_logger = (
        setup_child_logger("armonix.statemanager", parent_logger)
        if parent_logger
        else logging.getLogger("armonix.statemanager")
    )
    return StateManager(
        verbose=verbose,
        master=master,
        disable_realtime_display=disable_realtime_display,
        master_port_keyword=master_port_keyword,
        ketron_port_keyword=ketron_port_keyword,
        ble_port_keyword=ble_port_keyword,
        keypad_device=keypad_device,
        enable_midi_io=enable_midi_io,
        logger=state_logger,
    )


def ensure_session_credentials(logger: logging.Logger, session) -> bool:
    """Drop privileges to match the session user. / Riduce i privilegi per allinearsi all'utente della sessione."""

    try:
        current_uid = os.getuid()
        current_gid = os.getgid()
    except OSError:
        current_uid = current_gid = -1

    if current_uid == session.uid and current_gid == session.gid:
        return True

    if current_uid != 0:
        logger.warning(
            "Unable to adopt user '%s' (uid=%s): running as uid=%s.",
            session.username,
            session.uid,
            current_uid,
        )
        logger.warning(
            "Impossibile adottare l'utente '%s' (uid=%s): processo avviato con uid=%s.",
            session.username,
            session.uid,
            current_uid,
        )
        return False

    try:
        os.initgroups(session.username, session.gid)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Unable to configure supplementary groups for '%s': %s",
            session.username,
            exc,
        )
        logger.warning(
            "Impossibile impostare i gruppi supplementari per '%s': %s",
            session.username,
            exc,
        )

    try:
        os.setgid(session.gid)
        os.setuid(session.uid)
    except OSError as exc:
        logger.error(
            "Cannot change privileges to user '%s' (uid=%s): %s",
            session.username,
            session.uid,
            exc,
        )
        logger.error(
            "Impossibile impostare i permessi dell'utente '%s' (uid=%s): %s",
            session.username,
            session.uid,
            exc,
        )
        return False

    logger.info(
        "Continuing execution as user '%s' (uid=%s).",
        session.username,
        session.uid,
    )
    logger.info(
        "Esecuzione continuata come utente '%s' (uid=%s).",
        session.username,
        session.uid,
    )
    return True
