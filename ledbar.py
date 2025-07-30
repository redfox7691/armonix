from PyQt5 import QtCore, QtGui, QtWidgets

class LedBar(QtWidgets.QWidget):
    def __init__(self, states_getter):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(900, 38, 120, 38)
        self.led_letters = ['F', 'E', 'K', 'B', 'X']
        self.states_getter = states_getter
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
        led_x_start = 10 + 4 * 22
        if led_x_start <= x <= led_x_start + 20:
            if self.state_manager:
                self.state_manager.toggle_enabled()
            else:
                print("LED X cliccato (nessuna funzione collegata)")

    def set_state_manager(self, sm):
        self.state_manager = sm
