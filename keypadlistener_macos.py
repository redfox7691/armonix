"""Keypad listener per macOS basato su pynput.

Su Linux il tastierino USB viene letto direttamente da /dev/input tramite
evdev, che permette di filtrare per dispositivo.  Su macOS questo non è
possibile: pynput intercetta tutti gli eventi tastiera a livello di sistema
(richiede il permesso Accessibilità in Preferenze di Sistema).

Il parametro ``device`` del costruttore è ignorato su macOS — si consiglia
di usare un tastierino USB dedicato per evitare interferenze con la tastiera
principale del Mac.

Interfaccia identica a keypadlistener.KeypadListener per consentire
l'import condizionale in statemanager.py.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger("armonix.keypad")


class KeypadListener(threading.Thread):
    """Ascolta gli eventi tastiera globali tramite pynput e li inoltra via callback.

    Args:
        device:     Ignorato su macOS (mantenuto per compatibilità con l'interfaccia Linux).
        callback:   ``callback(scancode, keycode, is_down)`` chiamata per ogni evento.
        stop_event: Impostare per fermare il listener.
        verbose:    Se True stampa ogni evento ricevuto.
    """

    def __init__(
        self,
        device: str,
        callback: Callable,
        stop_event: threading.Event,
        verbose: bool = False,
    ) -> None:
        super().__init__(daemon=True)
        self.callback = callback
        self.stop_event = stop_event
        self.verbose = verbose
        # 'device' è ignorato su macOS
        if verbose:
            logger.debug(
                "KeypadListener macOS: parametro device='%s' ignorato "
                "(pynput ascolta tutti gli eventi tastiera)",
                device,
            )

    def run(self) -> None:
        try:
            from pynput import keyboard  # type: ignore
        except ImportError:
            logger.error(
                "pynput non trovato. Installalo con: pip install pynput\n"
                "Il tastierino USB non sarà disponibile."
            )
            return

        def _on_press(key):
            if self.stop_event.is_set():
                return False  # ferma il listener
            try:
                scancode = getattr(key, "vk", None)
                keycode = str(key)
                self.callback(scancode, keycode, True)
                if self.verbose:
                    print(f"[KEYPAD-MACOS] press  scancode={scancode} key={keycode}")
            except Exception as exc:
                logger.debug("Errore in on_press: %s", exc)

        def _on_release(key):
            if self.stop_event.is_set():
                return False  # ferma il listener
            try:
                scancode = getattr(key, "vk", None)
                keycode = str(key)
                self.callback(scancode, keycode, False)
                if self.verbose:
                    print(f"[KEYPAD-MACOS] release scancode={scancode} key={keycode}")
            except Exception as exc:
                logger.debug("Errore in on_release: %s", exc)

        with keyboard.Listener(on_press=_on_press, on_release=_on_release) as listener:
            self.stop_event.wait()
            listener.stop()
