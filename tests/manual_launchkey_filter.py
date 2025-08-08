"""Manual tests for `filter_and_translate_launchkey_msg`.

Run this file directly to verify that only messages on channel 1 (mido
channel 0) are forwarded to the Ketron output port.

La libreria `mido` non è necessaria per questo test: viene utilizzata una
semplice classe `FakeMessage` con il solo attributo `channel`.
"""

import os
import sys
import types

# Creazione di un modulo "mido" fittizio per evitare dipendenze esterne.
mido_stub = types.ModuleType("mido")

def _dummy_open_output(*args, **kwargs):
    class _DummyPort:
        name = "dummy"

        def send(self, msg):
            pass

    return _DummyPort()

mido_stub.open_output = _dummy_open_output
sys.modules["mido"] = mido_stub

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from launchkey_midi_filter import filter_and_translate_launchkey_msg


class DummyPort:
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)
        print(f"SENT TO KETRON: {msg}")


class FakeMessage:
    """Minimal replacement for mido.Message used in manual tests."""

    def __init__(self, channel):
        self.channel = channel

    def __repr__(self):
        return f"FakeMessage(channel={self.channel})"


def run():
    port = DummyPort()

    print("-- Sending channel 0 (should pass) --")
    msg0 = FakeMessage(channel=0)
    filter_and_translate_launchkey_msg(msg0, port, None, verbose=True)

    print("-- Sending channel 1 (should be ignored) --")
    msg1 = FakeMessage(channel=1)
    filter_and_translate_launchkey_msg(msg1, port, None, verbose=True)

    assert port.sent == [msg0], "Channel filtering failed"


if __name__ == "__main__":
    run()

