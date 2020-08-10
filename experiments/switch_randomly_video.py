import time
import random

from flyvr.control.experiment import Experiment


class _MyExperiment(Experiment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._t = time.time()

    def process_state(self, state):
        dt = time.time() - self._t
        if dt > 5:
            stim = random.choice(('v_loom_stim', 'v_move_sq'))
            self.play_playlist_item(Experiment.BACKEND_VIDEO, stim)
            self._t = time.time()


experiment = _MyExperiment()