import numpy as np

from control.motor_control import BallControl
from audio.signal_producer import MixedSignal
from audio.stimuli import SinStim, AudioStimPlaylist
from control.two_photon_control import TwoPhotonController


def test_ball_control_signal():

    ball_control = BallControl(num_samples_period=8)

    gen = ball_control.data_generator()

    for i in range(3):
        chunk = next(gen).data
        assert(np.array_equal(chunk[:, 0], np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)))
        assert(np.array_equal(chunk[:, 1], np.array([0, 0, 1, 1, 1, 1, 0, 0], dtype=np.uint8)))

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

    ball_control = BallControl(num_samples_period=8)

    mixed = MixedSignal([two_photon_controller, ball_control])

    gen = mixed.data_generator()

    chunk = next(gen).data

    assert(chunk.shape[1] == 5)