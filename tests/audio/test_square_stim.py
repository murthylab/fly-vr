import numpy as np
from scipy import signal
from audio.stimuli import SquareWaveStim


def test_square_stim():
    stim = SquareWaveStim(frequency=5, duty_cycle=0.5, amplitude=1, sample_rate=500, duration=1000)

    assert(np.array_equal(stim.data, signal.square(np.linspace(0, 1, 500)*2*np.pi*5)))

