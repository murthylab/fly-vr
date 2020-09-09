import time
import random

from flyvr.control.experiment import Experiment


class _MyExperiment(Experiment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def process_state(self, state):
        x = random.random()
        self.item_mutate(self.BACKEND_VIDEO,
                         'v_stim', 'obj1_x', x)

experiment = _MyExperiment()