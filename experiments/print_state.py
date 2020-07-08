from flyvr.control.experiment import Experiment


class _MyExperiment(Experiment):

    def __init__(self, *args, **kwargs):
        # need to do this dance to bind this function locally because globals() here do not propagate into
        # the rest of the flyvr when this file is exec()'d as an experiment later

        from flyvr.fictrac.shmem_transfer_data import print_fictrac_state
        self._print_state = print_fictrac_state

        super().__init__(*args, **kwargs)

    def process_state(self, state):
        self._print_state(state)


experiment = _MyExperiment()
