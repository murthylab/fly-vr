import pytest
import math
from unittest import mock
import numpy as np

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
    stims = [stim1, stim2, stim3]

    stimList = AudioStimPlaylist(stims, shuffle_playback=False)

    # Get the generator
    playGen = stimList.data_generator()

    # See if we can do looping sequential playback
    for i in range(0,5):
        assert (next(playGen).data == stims[i % 3].data).all()

    # Now lets check if shuffle is working. Make sure no stimulus is repeating.
    stimList = AudioStimPlaylist([stim1, stim2, stim3], shuffle_playback=True)

    # Get the generator
    playGen = stimList.data_generator()

    # Get the shuffle order, use the same seed as the playlist
    rng = np.random.RandomState()
    rng.seed(stimList.random_seed)
    order = rng.permutation(len(stims))

    for i in range(0,3):
        assert (next(playGen).data == stims[order[i]].data).all()

    # Get the next stimulus, this should cause the shuffle order to be reset
    rand_stim = next(playGen)

    # Get the new shuffle order
    order = rng.permutation(len(stims))

    assert((rand_stim.data == stims[order[0]].data).all)

    for i in range(1,3):
        assert (next(playGen).data == stims[order[i]].data).all()


def test_callbacks(stim1, stim2, stim3):
    stims = [stim1, stim2, stim3]

    my_callback_mock = mock.Mock()

    stimList = AudioStimPlaylist(stims, shuffle_playback=False, next_event_callbacks=my_callback_mock)

    data_gen = stimList.data_generator()

    next(data_gen)

    my_callback_mock.assert_called()

    # Now lets put a different callback on each stimuli
    callback1 = mock.Mock()
    callback2 = mock.Mock()

    s1 = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
            duration=200, intensity=1.0, pre_silence=0, post_silence=0,
            attenuator=None, next_event_callbacks=callback1)
    s2 = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                 duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                 attenuator=None, next_event_callbacks=callback2)

    stimList = AudioStimPlaylist([s1, s2], shuffle_playback=False)

    data_gen = stimList.data_generator()

    next(data_gen)

    callback1.assert_called_once()

    next(data_gen)

    callback1.assert_called_once()
    callback2.assert_called_once()


def test_multi_channel_playlist():
    import os.path

    PATH = 'tests/test_data/opto_control_playlist.txt'

    stimList = AudioStimPlaylist.fromfilename(PATH)
    gen = chunker(stimList.data_generator(), 1000)
    chunk = next(gen).data
    assert(chunk.shape[1] == 4)
    assert(stimList.num_channels == 4)

    with open(PATH, 'rt') as f:
        stims = legacy_factory(f.readlines(), os.path.dirname(PATH))
        print(stims)

    stimList = AudioStimPlaylist(stims)
    gen = chunker(stimList.data_generator(), 1000)
    chunk = next(gen).data
    assert(chunk.shape[1] == 4)
    assert(stimList.num_channels == 4)


def test_no_side_effects(stim1, stim2, stim3):
    stims = [stim1, stim2, stim3]

    stimList = AudioStimPlaylist(stims, shuffle_playback=False)

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