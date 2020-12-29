import collections

import numpy as np

from flyvr.control.experiment import Experiment

# A small experiment for printing when the fly (ball) speed
# exceeds on average SPEED_THRESHOLD over FILTER_LEN periods
# (1 period = 1 frame = 1/fps)

# This small 'experiment' should be run by the single
# flyvr-experiment program - while the rest of flyvr is
# running. That means
# $ flyvr.exe -c XX.yaml -p YY.yaml
#   (where neither the config XX.yml nor YY.yaml)


class _MyExperiment(Experiment):

    SPEED_THRESHOLD = 0.03
    FILTER_LEN = 33

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._speed_hist = collections.deque(maxlen=self.FILTER_LEN)

    def process_state(self, state):
        self._speed_hist.append(state.speed)
        if np.mean(state.speed) > self.SPEED_THRESHOLD:
            print("SPIN ", state.frame_cnt, "=", np.mean(state.speed))


experiment = _MyExperiment()
