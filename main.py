import argparse
import logging
import sys
import time
from logging.handlers import SysLogHandler

from configuration import load_config
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

    wifi_launcher = None
    if config.wifi.enabled:
        wifi_logger = logging.getLogger("armonix.wifi")
        wifi_launcher = WifiVncLauncher(config.wifi, logger=wifi_logger)
        wifi_launcher.start()

    try:
        if args.headless:
            logger.info("Modalità headless attiva")
            while True:
                time.sleep(1)
        else:
            logger.info("Modalità grafica attiva")
            from PyQt5 import QtWidgets
            from ledbar import LedBar

            app = QtWidgets.QApplication(sys.argv)
            led_bar = LedBar(states_getter=state_manager.get_led_states)
            state_manager.set_ledbar(led_bar)
            led_bar.set_state_manager(state_manager)
            app.exec_()
    except KeyboardInterrupt:
        logger.info("Terminazione richiesta dall'utente")
    except Exception:
        logger.exception("Errore non gestito")
        raise
    finally:
        if wifi_launcher:
            wifi_launcher.stop()


if __name__ == "__main__":
    main()
