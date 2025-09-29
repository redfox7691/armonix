"""Mouse control IPC helpers for Armonix."""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import threading
from typing import Optional


SOCKET_PATH = "/tmp/armonix-mouse.sock"


def _ensure_logger(logger: Optional[logging.Logger]) -> logging.Logger:
    if logger is not None:
        return logger
    return logging.getLogger("armonix.mouse")


class MouseCommandServer:
    """Background server executing mouse commands via xdotool."""

    def __init__(self, socket_path: str = SOCKET_PATH, logger: Optional[logging.Logger] = None):
        self.socket_path = socket_path
        self.logger = _ensure_logger(logger)
        self._server_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start listening for mouse command requests."""

        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()

        if self.socket_path:
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                self.logger.error("Impossibile rimuovere il socket %s: %s", self.socket_path, exc)

        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_socket.bind(self.socket_path)
        try:
            os.chmod(self.socket_path, 0o666)
        except OSError as exc:
            self.logger.warning("Impossibile impostare i permessi del socket %s: %s", self.socket_path, exc)
        server_socket.listen(1)
        server_socket.settimeout(1.0)
        self._server_socket = server_socket

        self._thread = threading.Thread(target=self._serve_forever, name="ArmonixMouseServer", daemon=True)
        self._thread.start()
        self.logger.debug("Mouse IPC server avviato su %s", self.socket_path)

    def stop(self) -> None:
        """Stop the server and clean up resources."""

        self._stop_event.set()
        if self._server_socket is not None:
            try:
                self._server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._server_socket.close()
            self._server_socket = None

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

        if self.socket_path:
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                self.logger.warning("Impossibile rimuovere il socket %s: %s", self.socket_path, exc)

        self.logger.debug("Mouse IPC server arrestato")

    def _serve_forever(self) -> None:
        assert self._server_socket is not None
        while not self._stop_event.is_set():
            try:
                client, _ = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    break
                self.logger.exception("Errore durante l'attesa di connessioni IPC mouse")
                break

            with client:
                try:
                    payload = client.recv(4096)
                    if not payload:
                        continue
                    message = json.loads(payload.decode("utf-8"))
                    action = message.get("action")
                    x = int(message.get("x"))
                    y = int(message.get("y"))
                except Exception as exc:  # pragma: no cover - defensive programming
                    self.logger.warning("Richiesta IPC mouse non valida: %s", exc)
                    continue

                if action == "press":
                    self._execute_mouse_command(x, y, down=True)
                elif action == "release":
                    self._execute_mouse_command(x, y, down=False)
                else:
                    self.logger.warning("Azione mouse sconosciuta: %s", action)

    def _execute_mouse_command(self, x: int, y: int, *, down: bool) -> None:
        button_action = "mousedown" if down else "mouseup"
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=True)
            subprocess.run(["xdotool", button_action, "1"], check=True)
        except Exception as exc:  # pragma: no cover - external dependency
            if down:
                self.logger.error("Impossibile simulare pressione mouse (%s, %s): %s", x, y, exc)
            else:
                self.logger.error("Impossibile simulare rilascio mouse (%s, %s): %s", x, y, exc)


def _send_mouse_command(action: str, x: int, y: int, *, logger: Optional[logging.Logger] = None) -> None:
    log = _ensure_logger(logger)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(SOCKET_PATH)
            payload = json.dumps({"action": action, "x": int(x), "y": int(y)}).encode("utf-8")
            sock.sendall(payload)
    except FileNotFoundError:
        log.error("Socket IPC mouse non disponibile (%s)", SOCKET_PATH)
    except OSError as exc:
        log.error("Errore nella comunicazione con il servizio GUI per il mouse: %s", exc)


def send_mouse_press(x: int, y: int, *, logger: Optional[logging.Logger] = None) -> None:
    _send_mouse_command("press", x, y, logger=logger)


def send_mouse_release(x: int, y: int, *, logger: Optional[logging.Logger] = None) -> None:
    _send_mouse_command("release", x, y, logger=logger)
