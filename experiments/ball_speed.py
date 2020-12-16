import collections

import numpy as np

from flyvr.control.experiment import Experiment


class _MyExperiment(Experiment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._speed_hist = collections.deque(maxlen=33)

    def process_state(self, state):
        self._speed_hist.append(state.speed)
        if np.mean(state.speed) > 0.03:
            print(self.is_started(), self.is_backend_ready(Experiment.BACKEND_VIDEO), self.is_stopped())
            print("SPIN ", state.frame_cnt, "=", np.mean(state.speed))

experiment = _MyExperiment()
