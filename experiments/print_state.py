from flyvr.control.experiment import Experiment
from flyvr.fictrac.shmem_transfer_data import print_fictrac_state


class _MyExperiment(Experiment):

    def process_state(self, state):
        print_fictrac_state(state)


experiment = _MyExperiment()
