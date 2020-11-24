import unittest.mock

import numpy as np

from flyvr.audio.stimuli import MATFileStim


def test__generate_data():

    # Check the underlying data that has been generated from the parameters above.
    # These values are the expected values based on comparisons with the original
    # matlab code this was ported from
    stim = MATFileStim('tests/audio/pulseTrain_16IPI.mat', frequency=250, sample_rate=10000)

    assert stim.dtype == np.float64
    assert stim.data.dtype == np.float64
    assert len(stim.data) == 40320
    assert abs(stim.data[49] - 0.287053808324911) < 1e-08


def test_callbacks():

    my_callback_mock = unittest.mock.Mock()

    stim = MATFileStim('tests/audio/pulseTrain_16IPI.mat', frequency=250, sample_rate=10000,
                       next_event_callback=my_callback_mock)

    data_gen = stim.data_generator()

    next(data_gen)

    my_callback_mock.assert_called()
