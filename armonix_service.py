"""Core MIDI service entry point. / Punto di ingresso del servizio MIDI principale."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

from configuration import load_config
from services_common import LoggerWriter, configure_logging, create_state_manager
from version import __version__ as ARMONIX_VERSION


def main(argv: Optional[list[str]] = None) -> None:
    """Run the MIDI engine in headless mode. / Esegue il motore MIDI in modalità headless."""

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
        description="Armonix MIDI engine / Motore MIDI Armonix",
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

    parser.set_defaults(
        verbose=config.verbose,
        master=config.master,
        disable_realtime_display=config.disable_realtime_display,
        config=config.source_path,
    )

    args = parser.parse_args(remaining)

    logger = configure_logging(args.verbose)

    sys.stdout = LoggerWriter(logging.DEBUG)
    sys.stderr = LoggerWriter(logging.ERROR)

    logger.info(
        "Armonix %s engine started (config=%s, master=%s).",
        ARMONIX_VERSION,
        args.config,
        args.master,
    )
    logger.info(
        "Motore Armonix %s avviato (config=%s, master=%s).",
        ARMONIX_VERSION,
        args.config,
        args.master,
    )

    state_manager = create_state_manager(
        verbose=args.verbose,
        master=args.master,
        disable_realtime_display=args.disable_realtime_display,
        master_port_keyword=config.midi.master_port_keyword,
        ketron_port_keyword=config.midi.ketron_port_keyword,
        ble_port_keyword=config.midi.bluetooth_port_keyword,
        keypad_device=config.keypad_device,
        enable_midi_io=True,
        parent_logger=logger,
    )

    try:
        logger.info("Headless mode active. / Modalità headless attiva.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user. / Arresto richiesto dall'utente.")
    finally:
        # The state manager threads terminate automatically on exit. / I thread del state manager terminano automaticamente all'uscita.
        pass


if __name__ == "__main__":
    main()
