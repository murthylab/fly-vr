import time
import random

from flyvr.control.experiment import Experiment

# this experiment randomly chooses only corresponding playlist items across
# the audio and daq backend. for example, if the daq playlist as items with
# identifiers 'd1', 'd2', 'd3', and 'd4', and the audio playlist has items
# with identifiers 'a1', 'a2', and 'a3', then every SWITCH_SECONDS we random
# choose to play simultaneously only (`d1' and 'a1'), ('d2' and 'a2'), or
# ('d3' and 'a3')

SWITCH_SECONDS = 5


class _MyExperiment(Experiment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exp_started = False
        self._last_switch = None
        self._n_common_playlist_items = 0

    def process_state(self, state):
        if self._exp_started:
            t = time.time()
            if (t - self._last_switch) > SWITCH_SECONDS:
                idx = random.randint(0, self._n_common_playlist_items - 1)

                item_daq = self.configured_playlist_items[Experiment.BACKEND_DAQ][idx]
                self.play_playlist_item(Experiment.BACKEND_DAQ, item_daq)
                item_audio = self.configured_playlist_items[Experiment.BACKEND_AUDIO][idx]
                self.play_playlist_item(Experiment.BACKEND_AUDIO, item_audio)

                self.log.info('switched to daq:%s and audio:%s' % (item_daq, item_audio))

                self._last_switch = t
        else:
            if self.is_started() and \
                    self.is_backend_ready(Experiment.BACKEND_AUDIO) and \
                    self.is_backend_ready(Experiment.BACKEND_DAQ):
                self._exp_started = True
                self._last_switch = time.time() - SWITCH_SECONDS  # switch next loop

            self._n_common_playlist_items = min(len(self.configured_playlist_items[Experiment.BACKEND_DAQ]),
                                                len(self.configured_playlist_items[Experiment.BACKEND_AUDIO]))
            assert self._n_common_playlist_items > 0


experiment = _MyExperiment()
