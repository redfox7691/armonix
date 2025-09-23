"""VNC helper for the Armonix GUI service. / Helper VNC per il servizio GUI di Armonix."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Optional

from configuration import VncConfig

EVM_HOST = "192.168.5.1"


class VncLauncher(threading.Thread):
    """Launch the configured VNC command when the EVM is reachable. / Avvia il comando VNC quando l'EVM è raggiungibile."""

    def __init__(
        self,
        vnc_config: VncConfig,
        stop_event: Optional[threading.Event] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.config = vnc_config
        self.stop_event = stop_event or threading.Event()
        self.logger = logger or logging.getLogger(__name__)
        self._process: Optional[subprocess.Popen[str]] = None
        self._announced_reachable = False
        self._announced_waiting = False

    def _is_evm_reachable(self) -> bool:
        """Check if the EVM responds to ping. / Controlla se l'EVM risponde al ping."""

        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", EVM_HOST],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            return False
        return result.returncode == 0

    def _launch(self) -> None:
        """Launch the VNC client if not already running. / Avvia il client VNC se non è già in esecuzione."""

        if self._process and self._process.poll() is None:
            return

        env = os.environ.copy()
        try:
            self._process = subprocess.Popen(self.config.command, shell=True, env=env)
            self.logger.info(
                "EVM reachable: started VNC command '%s'. / EVM raggiungibile: avviato comando VNC '%s'.",
                self.config.command,
                self.config.command,
            )
        except Exception:  # pragma: no cover - defensive logging
            self.logger.exception(
                "Unable to start the configured VNC command. / Impossibile avviare il comando VNC configurato."
            )
            self._process = None

    def run(self) -> None:  # pragma: no cover - relies on external systems
        if not self.config.enabled:
            return

        self.logger.info(
            "Monitoring EVM connectivity to start VNC. / Monitoraggio connettività EVM per avviare VNC."
        )

        while not self.stop_event.is_set():
            if self._process and self._process.poll() is not None:
                self.logger.info(
                    "VNC command exited with code %s. / Comando VNC terminato con codice %s.",
                    self._process.returncode,
                    self._process.returncode,
                )
                self._process = None

            if self._is_evm_reachable():
                if not self._announced_reachable:
                    self.logger.info(
                        "EVM host %s responded to ping. / L'host EVM %s ha risposto al ping.",
                        EVM_HOST,
                        EVM_HOST,
                    )
                    self._announced_reachable = True
                    self._announced_waiting = False
                self._launch()
            else:
                if not self._announced_waiting:
                    self.logger.info(
                        "EVM not reachable, waiting... / EVM non raggiungibile, in attesa..."
                    )
                    self._announced_waiting = True
                    self._announced_reachable = False

            self.stop_event.wait(max(1, self.config.poll_interval))

    def stop(self) -> None:
        """Stop the monitoring thread. / Ferma il thread di monitoraggio."""

        self.stop_event.set()
        if self.is_alive():
            self.join(timeout=5)
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Unable to terminate the VNC command. / Impossibile terminare il comando VNC."
                )
