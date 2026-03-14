from PyQt5 import QtCore, QtGui, QtWidgets

class LedBar(QtWidgets.QWidget):
    def __init__(self, states_getter, shutdown_callback=None):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(900, 38, 120, 38)
        self.led_letters = ['M', 'E', 'K', 'B', 'X']
        self.states_getter = states_getter
        self.shutdown_callback = shutdown_callback
        self.state_manager = None  # Da settare se vuoi il click abilitato
        self.show()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(200)

        self.anim_state = 0
        self.animating = False

        self.setMouseTracking(True)

    def set_animating(self, animating):
        self.animating = animating
        if self.animating:
            self.timer.timeout.connect(self.animate)
        else:
            try:
                self.timer.timeout.disconnect(self.animate)
            except TypeError:
                pass

    def animate(self):
        self.anim_state = (self.anim_state + 1) % 5
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        states = self.states_getter()
        for i, state in enumerate(states):
            x = 10 + i * 22
            if isinstance(state, str):
                color = QtGui.QColor(state)
            elif state is True:
                color = QtGui.QColor('green')
            elif state == 'red':
                color = QtGui.QColor('red')
            elif state == 'yellow':
                color = QtGui.QColor('yellow')
            else:
                color = QtGui.QColor('black')
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtCore.Qt.white)
            painter.drawEllipse(x, 8, 20, 20)
            painter.setPen(QtCore.Qt.white if color != QtGui.QColor('black') else QtCore.Qt.black)
            painter.setFont(QtGui.QFont('Arial', 12, QtGui.QFont.Bold))
            painter.drawText(x + 5, 23, self.led_letters[i])

    def mousePressEvent(self, event):
        x = event.x()
        hit_any = any(10 + i * 22 <= x <= 10 + i * 22 + 20 for i in range(5))
        if not hit_any:
            return

        # Se Ketron non è connesso: qualsiasi LED apre il dialogo di spegnimento
        if self.state_manager and self.state_manager.ketron_port is None:
            self._ask_shutdown()
            return

        # Ketron connesso: solo il LED X (indice 4) attiva toggle
        led_x_start = 10 + 4 * 22
        if led_x_start <= x <= led_x_start + 20 and self.state_manager:
            self.state_manager.toggle_enabled()

    def _ask_shutdown(self):
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle("Armonix")
        dlg.setText("Terminare Armonix?")
        dlg.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowStaysOnTopHint)
        btn_si = dlg.addButton("SI", QtWidgets.QMessageBox.YesRole)
        btn_no = dlg.addButton("NO", QtWidgets.QMessageBox.NoRole)  # noqa: F841
        dlg.setStyleSheet(
            "QMessageBox { font-size: 18pt; }"
            "QPushButton { min-width: 90px; min-height: 55px;"
            "              font-size: 18pt; font-weight: bold;"
            "              padding: 10px 24px; }"
        )
        dlg.exec_()
        if dlg.clickedButton() is btn_si and self.shutdown_callback:
            self.shutdown_callback()

    def set_state_manager(self, sm):
        self.state_manager = sm
