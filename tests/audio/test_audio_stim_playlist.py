import pytest
import math
from unittest import mock
import numpy as np

from flyvr.common import Randomizer
from flyvr.audio.signal_producer import chunker
from flyvr.audio.stimuli import SinStim, AudioStimPlaylist
from flyvr.audio.stimuli import legacy_factory


@pytest.fixture
def stim1():
    return SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)


@pytest.fixture
def stim2():
    return SinStim(frequency=330, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)


@pytest.fixture
def stim3():
    return SinStim(frequency=430, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)


def test_generator(stim1, stim2, stim3):
    stims = (stim1, stim2, stim3)

    stimList = AudioStimPlaylist(stims,
                                 random=Randomizer(*[s.identifier for s in stims], mode=Randomizer.MODE_NONE,
                                                   repeat=100))

    # Get the generator
    playGen = stimList.data_generator()

    # See if we can do looping sequential playback
    for i in range(0, 5):
        assert (next(playGen).data == stims[i % 3].data).all()

    rs = 42

    # Now lets check if shuffle is working. Make sure no stimulus is repeating.
    stimList = AudioStimPlaylist(stims,
                                 random=Randomizer(*[s.identifier for s in stims],
                                                   mode=Randomizer.MODE_SHUFFLE_NON_REPEAT,
                                                   repeat=2, random_seed=rs))
    # Get the generator
    playGen = stimList.data_generator()

    # Get the shuffle order, use the same seed as the playlist
    rng = np.random.RandomState(seed=rs)

    stims = list(stims)
    rng.shuffle(stims)

    for s in stims:
        assert (next(playGen).data == s.data).all()

    rng.shuffle(stims)

    for s in stims:
        assert (next(playGen).data == s.data).all()


def test_multi_channel_playlist():
    import os.path

    PATH = 'tests/test_data/opto_control_playlist.txt'

    stimList = AudioStimPlaylist.from_legacy_filename(PATH)
    gen = chunker(stimList.data_generator(), 1000)
    chunk = next(gen).data
    assert (chunk.shape[1] == 4)
    assert (stimList.num_channels == 4)

    with open(PATH, 'rt') as f:
        stims = legacy_factory(f.readlines()[1:], os.path.dirname(PATH))
        print(stims)

    stimList = AudioStimPlaylist(stims)
    gen = chunker(stimList.data_generator(), 1000)
    chunk = next(gen).data
    assert (chunk.shape[1] == 4)
    assert (stimList.num_channels == 4)


def test_no_side_effects(stim1, stim2, stim3):
    stims = [stim1, stim2, stim3]

    stimList = AudioStimPlaylist(stims,
                                 random=Randomizer(*[s.identifier for s in stims], mode=Randomizer.MODE_NONE,
                                                   repeat=4))

    # Get the generator
    playGen = stimList.data_generator()

    # See if we can do looping sequential playback
    for i in range(6):
        assert (next(playGen).data == stims[i % 3].data).all()

    # Setting shuffle on the original object, should have no effect on the previously created generator
    stimList.shuffle_playback = True

    # See if we can do looping sequential playback
    for i in range(6):
        assert (next(playGen).data == stims[i % 3].data).all()

    with pytest.raises(AttributeError):
        # playlist repeats exhaused
        _ = next(playGen).data