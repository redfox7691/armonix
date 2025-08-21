import argparse
import json
import os
import threading
from datetime import datetime
import atexit

import mido
from PyQt5 import QtCore, QtWidgets

from footswitch_lookup import FOOTSWITCH_LOOKUP
from tabs_lookup import TABS_LOOKUP
from custom_sysex_lookup import CUSTOM_SYSEX_LOOKUP


DEBUG = False


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "launchkey_config.json")


# ---------------------------------------------------------------------------
# MIDI utilities
# ---------------------------------------------------------------------------


def _find_launchkey_port(port_list):
    """Return the first Launchkey DAW port from the given list."""
    debug_print("Searching for Launchkey ports in", port_list)
    for name in port_list:
        if "Launchkey" in name and "DAW" in name:
            debug_print("Found Launchkey port:", name)
            return name
    debug_print("No Launchkey port found")
    return None


def _send_color(outport, section, pid, color, mode="static"):
    """Send a color update to the Launchkey for a pad or control."""
    if color is None:
        return
    mode_alias = {"static": "stationary"}
    mode_to_channel = {"stationary": 0, "flashing": 1, "pulsing": 2}
    colormode = mode_alias.get(mode, mode)
    chan = mode_to_channel.get(colormode, 0)
    val = max(0, min(int(color), 127))
    pid = int(pid) & 0x7F
    if section == "NOTE":
        msg = mido.Message("note_on", channel=chan, note=pid, velocity=val)
    else:
        msg = mido.Message("control_change", channel=chan, control=pid, value=val)
    debug_print(
        f"Sending color: section={section} pid={pid} color={val} mode={colormode}"
    )
    outport.send(msg)


class MidiListener(threading.Thread):
    """Background thread listening for MIDI events."""

    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        in_name = _find_launchkey_port(mido.get_input_names())
        if in_name is None:
            raise RuntimeError("Launchkey MIDI input not found")
        self.port = mido.open_input(in_name)

    def run(self):
        for msg in self.port:
            debug_print("Received MIDI:", msg)
            self.callback(msg)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class ColorPickerDialog(QtWidgets.QDialog):
    """Dialog that lets the user pick a color via the Launchkey fader."""

    def __init__(self, outport, section, pid, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.outport = outport
        self.section = section
        self.pid = pid
        self.current = None

        self.label = QtWidgets.QLabel("Muovi il fader destro per scegliere il colore")
        self.val_label = QtWidgets.QLabel("-")
        ok_button = QtWidgets.QPushButton("OK")
        skip_button = QtWidgets.QPushButton("Senza colore")

        ok_button.clicked.connect(self.accept)
        skip_button.clicked.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.val_label)
        layout.addWidget(ok_button)
        layout.addWidget(skip_button)

    def update_color(self, value):
        self.current = value
        self.val_label.setText(str(value))
        _send_color(self.outport, self.section, self.pid, value)

    def get_color(self):
        result = self.exec_()
        if result == QtWidgets.QDialog.Accepted and self.current is not None:
            return int(self.current)
        return None


class AssignmentDialog(QtWidgets.QDialog):
    """Dialog for choosing action type, name and colors."""

    def __init__(self, outport, section, pid, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Configura {section} {pid}")
        self.outport = outport
        self.section = section
        self.pid = pid

        self.type_box = QtWidgets.QComboBox()
        self.type_box.addItems(["TABS", "FOOTSWITCH", "CUSTOM"])
        self.action_box = QtWidgets.QComboBox()
        self.type_box.currentTextChanged.connect(self._populate_actions)
        self._populate_actions(self.type_box.currentText())

        self.color_btn = QtWidgets.QPushButton("Colore")
        self.color_btn.clicked.connect(self._pick_color)
        self.color_on_btn = QtWidgets.QPushButton("Colore ON")
        self.color_on_btn.clicked.connect(lambda: self._pick_color("on"))
        self.color_off_btn = QtWidgets.QPushButton("Colore OFF")
        self.color_off_btn.clicked.connect(lambda: self._pick_color("off"))

        self.color = None
        self.color_on = None
        self.color_off = None

        form = QtWidgets.QFormLayout()
        form.addRow("Tipo", self.type_box)
        form.addRow("Azione", self.action_box)
        form.addRow(self.color_btn)
        form.addRow(self.color_on_btn)
        form.addRow(self.color_off_btn)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btn_box)

    def _populate_actions(self, atype):
        self.action_box.clear()
        if atype == "TABS":
            self.action_box.addItems(sorted(TABS_LOOKUP.keys()))
            self.color_btn.setEnabled(True)
            self.color_on_btn.setEnabled(False)
            self.color_off_btn.setEnabled(False)
        elif atype == "FOOTSWITCH":
            self.action_box.addItems(sorted(FOOTSWITCH_LOOKUP.keys()))
            self.color_btn.setEnabled(True)
            self.color_on_btn.setEnabled(False)
            self.color_off_btn.setEnabled(False)
        else:
            self.action_box.addItems(sorted(CUSTOM_SYSEX_LOOKUP.keys()))
            self.color_btn.setEnabled(False)
            self.color_on_btn.setEnabled(True)
            self.color_off_btn.setEnabled(True)

    def _pick_color(self, which=None):
        dlg = ColorPickerDialog(
            self.outport,
            self.section,
            self.pid,
            "Scegli colore",
            self,
        )
        color = dlg.get_color()
        if which == "on":
            self.color_on = color
        elif which == "off":
            self.color_off = color
        else:
            self.color = color

    def get_entry(self):
        if self.exec_() != QtWidgets.QDialog.Accepted:
            return None
        entry = {
            "type": self.type_box.currentText(),
            "name": self.action_box.currentText(),
            "channel": 0,
        }
        if self.section == "NOTE":
            entry["note"] = int(self.pid)
        else:
            entry["control"] = int(self.pid)
        if self.color is not None:
            entry["color"] = int(self.color)
            entry["colormode"] = "static"
        if self.color_on is not None:
            entry["color_on"] = int(self.color_on)
        if self.color_off is not None:
            entry["color_off"] = int(self.color_off)
        return entry


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class ConfigWindow(QtWidgets.QWidget):
    def __init__(self, outport):
        super().__init__()
        self.setWindowTitle("Launchkey Config")
        self.outport = outport
        self.config = self._load_config()
        self.current_color_dialog = None

        self.label = QtWidgets.QLabel("Premi un controllo sulla Launchkey per configurarlo")
        self.save_btn = QtWidgets.QPushButton("SALVA")
        self.save_btn.clicked.connect(self.save_config)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.save_btn)

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return {"NOTE": [], "CC": []}
        with open(CONFIG_PATH) as f:
            lines = [line for line in f if not line.strip().startswith("//")]
        try:
            data = json.loads("".join(lines))
        except json.JSONDecodeError:
            return {"NOTE": [], "CC": []}
        data.setdefault("NOTE", [])
        data.setdefault("CC", [])
        return data

    def _update_entry(self, section, key, pid, entry):
        entries = self.config.setdefault(section, [])
        for i, existing in enumerate(entries):
            if existing.get(key) == pid:
                entries[i] = entry
                break
        else:
            entries.append(entry)

    @QtCore.pyqtSlot(object)
    def handle_midi(self, msg):
        debug_print("Handling MIDI:", msg)
        if (
            self.current_color_dialog
            and msg.type == "control_change"
            and msg.control == 61
            and msg.channel == 15
        ):
            self.current_color_dialog.update_color(msg.value)
            return

        if msg.type == "note_on" and msg.velocity > 0:
            dlg = AssignmentDialog(self.outport, "NOTE", msg.note, self)
            entry = dlg.get_entry()
            if entry:
                self._update_entry("NOTE", "note", msg.note, entry)
        elif (
            msg.type == "control_change"
            and msg.control != 61
            and msg.value > 0
        ):
            dlg = AssignmentDialog(self.outport, "CC", msg.control, self)
            entry = dlg.get_entry()
            if entry:
                self._update_entry("CC", "control", msg.control, entry)

    def save_config(self):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        if os.path.exists(CONFIG_PATH):
            backup = os.path.join(BASE_DIR, f"launchkey_config_{timestamp}.json")
            os.rename(CONFIG_PATH, backup)
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=2)
        QtWidgets.QMessageBox.information(self, "Salvato", "Configurazione salvata")


# ---------------------------------------------------------------------------
# Application startup
# ---------------------------------------------------------------------------


def main(debug=False):
    global DEBUG
    DEBUG = debug
    if DEBUG:
        debug_print("Debug mode enabled")

    out_name = _find_launchkey_port(mido.get_output_names())
    if out_name is None:
        raise RuntimeError("Launchkey MIDI output not found")
    debug_print("Opening output port:", out_name)
    outport = mido.open_output(out_name)

    # Enable DAW mode
    daw_on = mido.Message("note_on", channel=15, note=12, velocity=127)
    debug_print("Enabling DAW mode")
    outport.send(daw_on)

    # Ensure DAW mode is disabled on exit
    def _disable_daw():
        debug_print("Disabling DAW mode")
        outport.send(mido.Message("note_on", channel=15, note=12, velocity=0))

    atexit.register(_disable_daw)

    app = QtWidgets.QApplication([])
    win = ConfigWindow(outport)
    win.show()

    def midi_cb(msg):
        QtCore.QMetaObject.invokeMethod(
            win, "handle_midi", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(object, msg)
        )

    listener = MidiListener(midi_cb)
    listener.start()

    app.exec_()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configure Launchkey colors")
    parser.add_argument(
        "--debug", action="store_true", help="Stampa informazioni di debug"
    )
    args = parser.parse_args()
    main(debug=args.debug)
