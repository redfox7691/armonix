"""Client JSON-RPC minimale per Pianoteq."""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)


def load_preset(url, preset_name, timeout=2.0):
    """Invia loadPreset a Pianoteq via JSON-RPC. Restituisce True se riuscito."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "loadPreset",
        "params": [preset_name],
        "id": 1,
    }).encode()
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
        if "error" in result:
            logger.error("Pianoteq loadPreset errore: %s", result["error"])
            return False
        logger.info("Pianoteq preset caricato: %s", preset_name)
        return True
    except Exception as exc:
        logger.error("Pianoteq JSON-RPC non raggiungibile: %s", exc)
        return False
