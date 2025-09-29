"""Graphical helper service for Armonix. / Servizio grafico di supporto per Armonix."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

from configuration import load_config
from ledbar import LedBar
from services_common import (
    LoggerWriter,
    configure_logging,
    create_state_manager,
    setup_child_logger,
)
from mouse_ipc import MouseCommandServer
from vnc_launcher import VncLauncher
from version import __version__ as ARMONIX_VERSION


def main(argv: Optional[list[str]] = None) -> None:
    """Run the GUI/VNC service. / Esegue il servizio GUI/VNC."""

    if argv is None:
        argv = sys.argv[1:]

    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument(
        "--config",
        help="Override configuration file path. / Percorso alternativo del file di configurazione.",
        default=None,
    )
    base_args, remaining = base_parser.parse_known_args(argv)

    config = load_config(base_args.config)

    parser = argparse.ArgumentParser(
        description="Armonix GUI helper / Supporto GUI di Armonix",
        parents=[base_parser],
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Enable verbose logging. / Abilita il logging dettagliato.",
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
        help="Select the connected master keyboard. / Seleziona la master keyboard collegata.",
    )
    parser.add_argument(
        "--disable_realtime_display",
        dest="disable_realtime_display",
        action="store_true",
        help="Disable the realtime display on the keyboard. / Disabilita il display in tempo reale sulla tastiera.",
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
        help="Run without Qt LED bar. / Esegue senza la barra LED Qt.",
    )
    parser.add_argument(
        "--gui",
        dest="headless",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--enable-vnc",
        dest="launch_vnc",
        action="store_true",
        help="Launch the configured VNC client. / Avvia il client VNC configurato.",
    )
    parser.add_argument(
        "--disable-vnc",
        dest="launch_vnc",
        action="store_false",
        help=argparse.SUPPRESS,
    )

    parser.set_defaults(
        verbose=config.verbose,
        master=config.master,
        disable_realtime_display=config.disable_realtime_display,
        headless=config.headless,
        launch_vnc=config.vnc.enabled,
        config=config.source_path,
    )

    args = parser.parse_args(remaining)

    logger = configure_logging(args.verbose)
    sys.stdout = LoggerWriter(logging.DEBUG)
    sys.stderr = LoggerWriter(logging.ERROR)

    logger.info(
        "Armonix %s GUI helper started (config=%s, master=%s, mode=%s).",
        ARMONIX_VERSION,
        args.config,
        args.master,
        "headless" if args.headless else "gui",
    )
    logger.info(
        "Supporto GUI Armonix %s avviato (config=%s, master=%s, modalità=%s).",
        ARMONIX_VERSION,
        args.config,
        args.master,
        "headless" if args.headless else "gui",
    )

    vnc_logger = setup_child_logger("armonix.vnc", logger)
    mouse_logger = setup_child_logger("armonix.mouse", logger)

    if args.headless:
        _run_background_helpers(config, args, logger, vnc_logger, mouse_logger)
    else:
        _run_gui_helpers(config, args, logger, vnc_logger, mouse_logger)


def _run_background_helpers(config, args, logger, vnc_logger, mouse_logger) -> None:
    """Run without the Qt LED bar. / Esegue senza la barra LED Qt."""

    launcher: Optional[VncLauncher] = None
    mouse_server = MouseCommandServer(logger=mouse_logger)
    try:
        mouse_server.start()
        if args.launch_vnc and config.vnc.enabled:
            launcher = VncLauncher(config.vnc, logger=vnc_logger)
            launcher.start()
        logger.info("Background mode active. / Modalità in background attiva.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user. / Arresto richiesto dall'utente.")
    finally:
        mouse_server.stop()
        if launcher:
            launcher.stop()


def _run_gui_helpers(config, args, logger, vnc_logger, mouse_logger) -> None:
    """Start the Qt LED bar and optional VNC watcher. / Avvia la barra LED Qt e il monitor VNC opzionale."""

    try:
        from PyQt5 import QtWidgets
    except ImportError as exc:  # pragma: no cover - optional dependency
        logger.error(
            "PyQt5 is required for the GUI mode: %s. / PyQt5 è necessario per la modalità GUI: %s.",
            exc,
            exc,
        )
        raise SystemExit(1) from exc

    launcher: Optional[VncLauncher] = None
    mouse_server = MouseCommandServer(logger=mouse_logger)
    state_manager = create_state_manager(
        verbose=args.verbose,
        master=args.master,
        disable_realtime_display=args.disable_realtime_display,
        master_port_keyword=config.midi.master_port_keyword,
        ketron_port_keyword=config.midi.ketron_port_keyword,
        ble_port_keyword=config.midi.bluetooth_port_keyword,
        keypad_device=config.keypad_device,
        enable_midi_io=False,
        parent_logger=logger,
    )

    app = QtWidgets.QApplication(sys.argv)
    led_bar = LedBar(states_getter=state_manager.get_led_states)
    state_manager.set_ledbar(led_bar)
    led_bar.set_state_manager(state_manager)

    try:
        mouse_server.start()
        if args.launch_vnc and config.vnc.enabled:
            launcher = VncLauncher(config.vnc, logger=vnc_logger)
            launcher.start()
        logger.info("Qt LED bar running. / Barra LED Qt in esecuzione.")
        app.exec_()
    finally:
        if launcher:
            launcher.stop()
        led_bar.close()
        state_manager.set_ledbar(None)
        mouse_server.stop()


if __name__ == "__main__":
    main()
