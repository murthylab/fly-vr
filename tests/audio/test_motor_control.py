import numpy as np
import h5py as h5

from control.motor_control import BallControlSignal
from audio.signal_producer import MixedSignal
from audio.stimuli import SinStim, AudioStimPlaylist
from control.two_photon_control import TwoPhotonController


def test_ball_control_signal():

    # Lets try a single signal.
    ball_control = BallControlSignal(periods=[0.8], durations=[0.8/1000])
    gen = ball_control.data_generator()
    for i in range(3):
        chunk = next(gen).data
        assert(np.array_equal(chunk[:, 0], np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)))
        assert(np.array_equal(chunk[:, 1], np.array([0, 0, 1, 1, 1, 1, 0, 0], dtype=np.uint8)))

    # Lets try two signals
    ball_control = BallControlSignal(periods=[0.8, 1.6], durations=[0.8 / 1000, 1.6 / 1000])
    gen = ball_control.data_generator()
    for i in range(3):
        chunk = next(gen).data
        assert (np.array_equal(chunk[:, 0], np.array([1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)))
        assert (np.array_equal(chunk[:, 1], np.array([0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)))

    # Lets try an odd and even signal. With no looping.
    ball_control = BallControlSignal(periods=[1, 2], durations=[2, 3], loop=False)
    gen = ball_control.data_generator()
    for i in range(3):
        chunk = next(gen).data

        # Check that the length if 50000 or 5 seconds
        assert(chunk.shape[0] == 5*10000)

        # We are no looping, so the next yield should be all zeros.
        if i > 0:
            assert(np.all(chunk == 0))

def test_mixed_control():
    stim1 = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    stim2 = SinStim(frequency=430, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    stimList = AudioStimPlaylist([stim1, stim2], shuffle_playback=False)

    two_photon_controller = TwoPhotonController(start_channel_name="",
                                                stop_channel_name="",
                                                next_file_channel_name="",
                                                audio_stim_playlist=stimList)

    ball_control = BallControlSignal(periods=[0.8], durations=[0.8/1000])

    mixed = MixedSignal([two_photon_controller, ball_control])

    gen = mixed.data_generator()

    chunk = next(gen).data

    assert(chunk.shape[1] == 5)