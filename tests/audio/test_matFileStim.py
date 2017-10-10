import pytest
import math

from audio.stimuli import AudioStim, MATFileStim

def test__generate_data():

    # Check the underlying data that has been generated from the parameters above.
    # These values are the expected values based on comparisons with the original
    # matlab code this was ported from
    stim = MATFileStim('tests/audio/pulseTrain_16IPI.mat', frequency=250, sample_rate=10000)

    assert len(stim.data) == 40320
    assert abs(stim.data[49] - 0.287053808324911) < 1e-08