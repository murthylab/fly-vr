import pytest
from unittest import mock
import math

from audio.stimuli import AudioStim, SinStim

@pytest.fixture
def stim():

    stim = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)

    # Create a sin stimulus
    return stim

def test__generate_data(stim):

    # Check the underlying data that has been generated from the parameters above.
    # These values are the expected values based on comparisons with the original
    # matlab code this was ported from.
    assert len(stim.data) == 8000
    assert abs(stim.data[29] - 1.732705016743634) < 1e-08

def test_amplitude(stim):

    # Change the amplitude, see if data changes correctly
    stim.amplitude = 3
    assert abs(stim.data[29] - 2.599057525115452) < 1e-08

def test_phase(stim):

    # Change the phase, see if data changes correctly
    stim.phase = math.pi
    assert abs(stim.data[29] - -1.732705016743634) < 1e-08

def test_duration(stim):

    # Change the duration, make sure the length increases
    stim.duration = stim.duration * 2
    assert len(stim.data) == 16000

def test_presilence(stim):

    # Add some silence, make sure the data is regenerated and it works
    stim.pre_silence = 100
    assert stim.data[29] == 0.0

def test_intensity(stim):
    # Make sure intensity is working as a multiplicative factor
    oldVal = stim.data[29]
    stim.intensity = 2.0
    assert stim.data[29] == oldVal*2.0

def test_callbacks(stim):

    my_callback_mock = mock.Mock()

    stim = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None, next_event_callbacks=my_callback_mock)

    data_gen = stim.data_generator()

    next(data_gen)

    my_callback_mock.assert_called()