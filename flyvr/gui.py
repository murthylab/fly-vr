from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QGridLayout
from PyQt5.QtCore import QTimer

from flyvr.common import SharedState


class FlyVRStateGui(QWidget):

    STATE = ['FICTRAC_FRAME_NUM',
             'SOUND_OUTPUT_NUM_SAMPLES_WRITTEN',
             'VIDEO_OUTPUT_NUM_FRAMES',
             'DAQ_OUTPUT_NUM_SAMPLES_WRITTEN',
             'DAQ_INPUT_NUM_SAMPLES_READ']
    FPS = 30

    def __init__(self, app, quit_app_on_stop):
        # noinspection PyArgumentList
        super().__init__(parent=None)
        self._app = app
        self._quit_app_on_stop = quit_app_on_stop

        self._entries = {}

        self._lbl_backends = None
        self._lbl_started = None
        self._init_ui()

        self.flyvr_shared_state = SharedState(options=None,
                                              logger=None,
                                              where='gui')

        self._timer = QTimer()
        # noinspection PyUnresolvedReferences
        self._timer.timeout.connect(self._update_state)
        self._timer.start(1000 / FlyVRStateGui.FPS)

    def _update_state(self):
        for s in FlyVRStateGui.STATE:
            v = getattr(self.flyvr_shared_state, s)
            self._entries[s].setText(str(v or 0))

        self._lbl_backends.setText(', '.join(self.flyvr_shared_state.backends_ready))
        self._lbl_started.setText(str(self.flyvr_shared_state.is_started()))

        if self._quit_app_on_stop:
            if self.flyvr_shared_state.is_stopped():
                self._app.quit()

    def _clicked_clear(self):
        for s in FlyVRStateGui.STATE:
            self._entries[s].setText('')

    def _clicked_start(self):
        self.flyvr_shared_state.signal_start()

    def _clicked_stop(self):
        self.flyvr_shared_state.signal_stop().join(2)

    # noinspection PyUnresolvedReferences,PyArgumentList
    def _init_ui(self):
        self.setWindowTitle('FlyVR')

        layout = QGridLayout()

        # noinspection PyArgumentList
        def _build_label(_name, _row):
            _lbl = QLabel('&%s' % _name, self)
            _edt = QLineEdit(self)
            _edt.setReadOnly(True)
            _lbl.setBuddy(_edt)

            layout.addWidget(_lbl, _row, 0)
            layout.addWidget(_edt, _row, 1, 1, 2)

            return _edt

        row = 0
        for s in FlyVRStateGui.STATE:
            self._entries[s] = _build_label(s, row)
            row += 1

        self._lbl_backends = _build_label('Backends Ready', row)
        row += 1

        self._lbl_started = _build_label('Experiment Started', row)
        row += 1

        # clear = QPushButton('&Clear')
        # clear.clicked.connect(self._clicked_clear)
        # layout.addWidget(clear, row, 2)
        # row += 1

        start = QPushButton('&Start Experiment')
        start.clicked.connect(self._clicked_start)
        stop = QPushButton('&Stop FlyVR')
        stop.clicked.connect(self._clicked_stop)

        layout.addWidget(start, row, 1)
        layout.addWidget(stop, row, 2)

        row += 1

        self.setLayout(layout)


def run_main_state_gui(argv, quit_app_on_stop):
    app = QApplication(argv or [])
    main = FlyVRStateGui(app=app, quit_app_on_stop=quit_app_on_stop)
    main.show()
    return app.exec_()


if __name__ == '__main__':
    import sys
    sys.exit(run_main_state_gui(sys.argv,
                                quit_app_on_stop=False))
