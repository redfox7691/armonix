"""Helper per avviare Pianoteq se non è già in ascolto sulla porta MIDI."""

import subprocess
import time

import mido


def ensure_pianoteq_running(config, logger):
    """Return True if Pianoteq's ALSA MIDI port is reachable; launch it if not.

    The executable is started with ``--serve 127.0.0.1:8081`` so that the
    JSON-RPC API is also available for future preset control.
    """
    for name in mido.get_output_names():
        if config.port_keyword in name:
            logger.debug("Porta Pianoteq già disponibile: %s", name)
            return True

    if not config.executable:
        logger.warning("Pianoteq executable non configurato")
        return False

    logger.info("Avvio Pianoteq: %s", config.executable)
    try:
        subprocess.Popen(
            [config.executable, "--serve", "127.0.0.1:8081"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.error("Impossibile avviare Pianoteq: %s", exc)
        return False

    for _ in range(20):
        time.sleep(0.5)
        for name in mido.get_output_names():
            if config.port_keyword in name:
                logger.info("Porta Pianoteq disponibile dopo avvio: %s", name)
                return True

    logger.warning("Porta Pianoteq non trovata dopo l'avvio")
    return False
