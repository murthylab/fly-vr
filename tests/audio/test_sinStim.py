import pytest
import math

from audio.stimuli import AudioStim, SinStim

@pytest.fixture
def stim():

    # Create a sin stimulus
    return SinStim(230, 2.0, 0.0, 40000, 200, 0, 0)

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