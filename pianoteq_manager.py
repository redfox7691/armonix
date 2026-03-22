"""Helper per avviare Pianoteq se non è già in esecuzione."""

import shlex
import subprocess


def ensure_pianoteq_running(config, logger):
    """Avvia Pianoteq se non è già in esecuzione.

    Con l'architettura a porta virtuale "Armonix", non è necessario attendere
    che Pianoteq esponga la propria porta ALSA: le note arrivano alla porta
    virtuale indipendentemente.  Questa funzione si limita a:

    1. Verificare se il processo è già attivo (pgrep) → True immediato.
    2. Lanciarlo in background se l'eseguibile è configurato → True immediato.
    3. Restituire False solo se l'eseguibile non è configurato.
    """
    # 1. Processo già in esecuzione → niente da fare.
    if config.executable:
        try:
            result = subprocess.run(
                ["pgrep", "-f", config.executable],
                capture_output=True,
            )
            if result.returncode == 0:
                logger.debug("Processo Pianoteq già in esecuzione.")
                return True
        except FileNotFoundError:
            pass  # pgrep non disponibile, prosegui con l'avvio diretto

    if not config.executable:
        logger.warning("Pianoteq executable non configurato")
        return False

    # 2. Avvia Pianoteq in background senza attendere la porta ALSA.
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

    return True
