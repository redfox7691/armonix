"""Helper per avviare Pianoteq se non è già in ascolto sulla porta MIDI."""

import shlex
import subprocess
import time

import mido


def ensure_pianoteq_running(config, logger):
    """Return True if Pianoteq's ALSA MIDI port is reachable; launch it if not.

    The executable is started with ``--serve 127.0.0.1:8081`` plus any extra
    options specified in ``config.options``.  Before launching a new process the
    function checks both the ALSA port list and running processes to avoid
    starting a second instance.
    """
    # 1. Port already open → nothing to do.
    for name in mido.get_output_names():
        if config.port_keyword in name:
            logger.debug("Porta Pianoteq già disponibile: %s", name)
            return True

    if not config.executable:
        logger.warning("Pianoteq executable non configurato")
        return False

    # 2. Process already running but port not yet exposed → just wait.
    try:
        result = subprocess.run(
            ["pgrep", "-f", config.executable],
            capture_output=True,
        )
        if result.returncode == 0:
            logger.debug("Processo Pianoteq già in esecuzione, attendo porta MIDI...")
            for _ in range(20):
                time.sleep(0.5)
                for name in mido.get_output_names():
                    if config.port_keyword in name:
                        logger.info("Porta Pianoteq disponibile: %s", name)
                        return True
            logger.warning("Porta Pianoteq non trovata nonostante il processo sia attivo")
            return False
    except FileNotFoundError:
        pass  # pgrep non disponibile, prosegui con l'avvio diretto

    # 3. Launch Pianoteq.
    extra = shlex.split(config.options) if config.options.strip() else []
    cmd = [config.executable, "--serve", "127.0.0.1:8081"] + extra
    logger.info("Avvio Pianoteq: %s", " ".join(cmd))
    try:
        subprocess.Popen(
            cmd,
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
