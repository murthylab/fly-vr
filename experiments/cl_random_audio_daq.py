import collections

import numpy as np

from flyvr.control.experiment import Experiment

# this is an example 'closed-loop' experiment that plays a random
# item from the configured video and DAQ playlists every time the
# fly (ball) speed exceeds 0.03.
#
# note: it is likely that the SPEED_THRESHOLD and FILTER_LEN
#       might need to be tuned based on the actual fly and/or
#       the attachment of the stepper motor to the ball. you can
#       use experiments/print_ball_speed.py to test these values
#
# For testing, you can control the speed of the ball using
# the tests/ball_control_phidget/ball_control.py and passing it
# a desired speed. If it is run without arguments then it will
# randomly alternate between 2 speeds in both directions and stopped.
# if run with an argument, it will set the ball to that speed
# e.g.
#  $ python tests/ball_control_phidget/ball_control.py 600


class _MyExperiment(Experiment):

    SPEED_THRESHOLD = 0.03
    FILTER_LEN = 33

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rand = np.random.RandomState()
        # a rolling list of the last N speed measurements, filtered
        # with np.mean to remove noise
        self._speed_hist = collections.deque(maxlen=self.FILTER_LEN)

    @property
    def is_started_and_ready_audio_daq(self):
        return self.is_started() and \
               self.is_backend_ready(Experiment.BACKEND_AUDIO) and \
               self.is_backend_ready(Experiment.BACKEND_DAQ)

    @property
    def is_started_and_ready_video(self):
        return self.is_started() and self.is_backend_ready(Experiment.BACKEND_VIDEO)

    def process_state(self, state):
        if self.is_started_and_ready_audio_daq:
            self._speed_hist.append(state.speed)
            if np.mean(state.speed) > self.SPEED_THRESHOLD:
                item_daq = self._rand.choice(self.configured_playlist_items[Experiment.BACKEND_DAQ])
                self.play_playlist_item(Experiment.BACKEND_DAQ, item_daq)
                item_audio = self._rand.choice(self.configured_playlist_items[Experiment.BACKEND_AUDIO])
                self.play_playlist_item(Experiment.BACKEND_AUDIO, item_audio)

                self.log.info('switched to daq:%s and audio:%s (speed=%s frame=%s)' % (
                    item_daq, item_audio, np.mean(state.speed), state.frame_cnt))


experiment = _MyExperiment()
