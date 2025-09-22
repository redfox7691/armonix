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

    wifi_launcher = None
    if config.wifi.enabled:
        wifi_logger = logging.getLogger("armonix.wifi")
        wifi_launcher = WifiVncLauncher(config.wifi, logger=wifi_logger)
        wifi_launcher.start()

    state_manager = StateManager(
        verbose=args.verbose,
        master=args.master,
        disable_realtime_display=args.disable_realtime_display,
        master_port_keyword=config.midi.master_port_keyword,
        ketron_port_keyword=config.midi.ketron_port_keyword,
        ble_port_keyword=config.midi.bluetooth_port_keyword,
        keypad_device=config.keypad_device,
        logger=logging.getLogger("armonix.statemanager"),
    )

    try:
        if args.headless:
            logger.info("Modalità headless attiva")
            while True:
                time.sleep(1)
        else:
            logger.info("Modalità grafica attiva")
            _run_gui_mode(
                config=config,
                logger=logger,
                state_manager=state_manager,
            )
    except KeyboardInterrupt:
        logger.info("Terminazione richiesta dall'utente")
    except Exception:
        logger.exception("Errore non gestito")
        raise
    finally:
        if wifi_launcher:
            wifi_launcher.stop()


def _run_gui_mode(config, logger, state_manager) -> None:
    from PyQt5 import QtCore, QtWidgets
    from ledbar import LedBar

    poll_interval = max(1, config.wifi.poll_interval)

    app: Optional[QtWidgets.QApplication] = None

    session_logger = logging.getLogger("armonix.gui")
    session_logger.propagate = False
    for handler in list(session_logger.handlers):
        session_logger.removeHandler(handler)
    for handler in logger.handlers:
        session_logger.addHandler(handler)
    session_logger.setLevel(logger.level)

    while True:
        session = _wait_for_graphical_session(session_logger, poll_interval)
        if not session:
            return

        env = build_session_environment(session)
        os.environ.update(env)

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
