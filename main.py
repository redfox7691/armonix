import argparse
import logging
import os
import sys
import threading
import time
from logging.handlers import SysLogHandler
from typing import Optional

from configuration import load_config
from session_utils import build_session_environment, find_active_graphical_session
from statemanager import StateManager
from wifi_vnc import WifiVncLauncher


class _LoggerWriter:
    """Redirect ``print`` output to the configured logger."""

    def __init__(self, level: int) -> None:
        self.level = level
        self.logger = logging.getLogger("armonix")

    def write(self, message: str) -> None:
        if not message:
            return
        message = message.rstrip()
        if not message:
            return
        for line in message.splitlines():
            self.logger.log(self.level, line)

    def flush(self) -> None:  # pragma: no cover - interface compatibility
        pass


def _configure_logging(verbose: bool) -> logging.Logger:
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


def _setup_child_logger(name: str, parent: logging.Logger) -> logging.Logger:
    """Create a child logger mirroring the parent's configuration."""

    child = logging.getLogger(name)
    child.propagate = False
    for handler in list(child.handlers):
        child.removeHandler(handler)
    for handler in parent.handlers:
        child.addHandler(handler)
    child.setLevel(parent.level)
    return child


def _create_state_manager(
    *,
    verbose: bool,
    master: str,
    disable_realtime_display: bool,
    master_port_keyword: Optional[str],
    ketron_port_keyword: Optional[str],
    ble_port_keyword: Optional[str],
    keypad_device: Optional[str],
    parent_logger: Optional[logging.Logger] = None,
) -> StateManager:
    state_logger = (
        _setup_child_logger("armonix.statemanager", parent_logger)
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
        logger=state_logger,
    )


def _ensure_session_credentials(logger: logging.Logger, session) -> bool:
    """Adopt the UID/GID of the graphical session when running as root."""

    try:
        current_uid = os.getuid()
        current_gid = os.getgid()
    except OSError:
        current_uid = current_gid = -1

    if current_uid == session.uid and current_gid == session.gid:
        return True

    if current_uid != 0:
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
            "Impossibile impostare i gruppi supplementari per '%s': %s",
            session.username,
            exc,
        )

    try:
        os.setgid(session.gid)
        os.setuid(session.uid)
    except OSError as exc:
        logger.error(
            "Impossibile impostare i permessi dell'utente '%s' (uid=%s): %s",
            session.username,
            session.uid,
            exc,
        )
        return False

    logger.info(
        "Esecuzione continuata come utente '%s' (uid=%s).",
        session.username,
        session.uid,
    )
    return True


def main() -> None:
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument(
        "--config", help="Percorso alternativo del file di configurazione", default=None
    )
    base_args, remaining = base_parser.parse_known_args()

    config = load_config(base_args.config)

    parser = argparse.ArgumentParser(
        description="ArmonixNG - MIDI System Control", parents=[base_parser]
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Abilita il logging dettagliato",
    )
    parser.add_argument(
        "--no-verbose",
        dest="verbose",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--master",
        choices=["fantom", "launchkey"],
        help="Specifica la master keyboard collegata",
    )
    parser.add_argument(
        "--disable_realtime_display",
        dest="disable_realtime_display",
        action="store_true",
        help="Disabilita la visualizzazione dei messaggi di controllo in tempo reale",
    )
    parser.add_argument(
        "--enable_realtime_display",
        dest="disable_realtime_display",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Esegui senza GUI e senza dipendenze PyQt5",
    )
    parser.add_argument(
        "--gui",
        dest="headless",
        action="store_false",
        help="Forza l'avvio con interfaccia grafica",
    )

    parser.set_defaults(
        verbose=config.verbose,
        master=config.master,
        disable_realtime_display=config.disable_realtime_display,
        headless=config.headless,
        config=config.source_path,
    )

    args = parser.parse_args(remaining)

    logger = _configure_logging(args.verbose)

    sys.stdout = _LoggerWriter(logging.DEBUG)
    sys.stderr = _LoggerWriter(logging.ERROR)

    logger.info(
        "Armonix 0.99 avviato (config=%s, master=%s, modalità=%s)",
        args.config,
        args.master,
        "headless" if args.headless else "gui",
    )

    wifi_logger = _setup_child_logger("armonix.wifi", logger)

    wifi_launcher = None
    state_manager = None

    try:
        if args.headless:
            if config.wifi.enabled:
                wifi_launcher = WifiVncLauncher(config.wifi, logger=wifi_logger)
                wifi_launcher.start()

            state_manager = _create_state_manager(
                verbose=args.verbose,
                master=args.master,
                disable_realtime_display=args.disable_realtime_display,
                master_port_keyword=config.midi.master_port_keyword,
                ketron_port_keyword=config.midi.ketron_port_keyword,
                ble_port_keyword=config.midi.bluetooth_port_keyword,
                keypad_device=config.keypad_device,
                parent_logger=logger,
            )

            logger.info("Modalità headless attiva")
            while True:
                time.sleep(1)
        else:
            logger.info("Modalità grafica attiva")
            _run_gui_mode(
                config=config,
                logger=logger,
                wifi_logger=wifi_logger,
                verbose=args.verbose,
                master=args.master,
                disable_realtime_display=args.disable_realtime_display,
                master_port_keyword=config.midi.master_port_keyword,
                ketron_port_keyword=config.midi.ketron_port_keyword,
                ble_port_keyword=config.midi.bluetooth_port_keyword,
                keypad_device=config.keypad_device,
            )
    except KeyboardInterrupt:
        logger.info("Terminazione richiesta dall'utente")
    except Exception:
        logger.exception("Errore non gestito")
        raise
    finally:
        if wifi_launcher:
            wifi_launcher.stop()


def _run_gui_mode(
    *,
    config,
    logger: logging.Logger,
    wifi_logger: logging.Logger,
    verbose: bool,
    master: str,
    disable_realtime_display: bool,
    master_port_keyword: Optional[str],
    ketron_port_keyword: Optional[str],
    ble_port_keyword: Optional[str],
    keypad_device: Optional[str],
) -> None:
    from PyQt5 import QtCore, QtWidgets
    from ledbar import LedBar

    poll_interval = max(1, config.wifi.poll_interval)

    app: Optional[QtWidgets.QApplication] = None

    session_logger = _setup_child_logger("armonix.gui", logger)

    wifi_launcher: Optional[WifiVncLauncher] = None
    state_manager: Optional[StateManager] = None
    credentials_ready = False

    try:
        while True:
            session = _wait_for_graphical_session(session_logger, poll_interval)
            if not session:
                return

            env = build_session_environment(session)
            os.environ.update(env)

            if not credentials_ready:
                credentials_ready = _ensure_session_credentials(session_logger, session)

            if state_manager is None:
                state_manager = _create_state_manager(
                    verbose=verbose,
                    master=master,
                    disable_realtime_display=disable_realtime_display,
                    master_port_keyword=master_port_keyword,
                    ketron_port_keyword=ketron_port_keyword,
                    ble_port_keyword=ble_port_keyword,
                    keypad_device=keypad_device,
                    parent_logger=logger,
                )

            if wifi_launcher is None and config.wifi.enabled:
                wifi_launcher = WifiVncLauncher(config.wifi, logger=wifi_logger)
                wifi_launcher.start()

            if app is None:
                app = QtWidgets.QApplication(sys.argv)

            led_bar = LedBar(states_getter=state_manager.get_led_states)
            state_manager.set_ledbar(led_bar)
            led_bar.set_state_manager(state_manager)
            session_logger.info(
                "Avvio della barra LED per l'utente '%s'.",
                session.username,
            )

            session_lost = threading.Event()

            def _request_quit() -> None:
                if session_lost.is_set():
                    return
                session_lost.set()
                QtCore.QTimer.singleShot(0, app.quit)

            monitor = _SessionMonitor(
                session_id=session.session_id,
                poll_interval=poll_interval,
                on_session_lost=_request_quit,
            )
            monitor.start()

            try:
                app.exec_()
            finally:
                monitor.stop()
                monitor.join()

                led_bar.close()
                state_manager.set_ledbar(None)

            if session_lost.is_set():
                session_logger.info(
                    "Sessione grafica terminata: in attesa di un nuovo login per riattivare la barra LED."
                )
                continue

            break
    finally:
        if wifi_launcher:
            wifi_launcher.stop()


class _SessionMonitor(threading.Thread):
    def __init__(self, session_id: str, poll_interval: int, on_session_lost) -> None:
        super().__init__(daemon=True)
        self.session_id = session_id
        self.poll_interval = max(1, poll_interval)
        self.on_session_lost = on_session_lost
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:  # pragma: no cover - system interaction
        while not self._stop_event.wait(self.poll_interval):
            session = find_active_graphical_session()
            if not session or session.session_id != self.session_id:
                self.on_session_lost()
                return


def _wait_for_graphical_session(logger, poll_interval: int):
    logged_waiting = False

    while True:
        session = find_active_graphical_session()
        if session:
            logger.info(
                "Sessione grafica rilevata per l'utente '%s' (display %s).",
                session.username,
                session.display or "n/d",
            )
            return session

        if not logged_waiting:
            logger.info(
                "Nessuna sessione grafica locale attiva: la barra LED verrà avviata non appena disponibile."
            )
            logged_waiting = True

        time.sleep(max(1, poll_interval))


if __name__ == "__main__":
    main()
