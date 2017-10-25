import pytest
import math
import mock

from audio.stimuli import SinStim, AudioStimPlaylist

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
        assert (playGen.next() == stims[i % 3].data).all()

    # Now lets check if shuffle is working. Make sure no stimulus is repeating.
    stimList = AudioStimPlaylist([stim1, stim2, stim3], shuffle_playback=True)

    # Get the generator
    playGen = stimList.data_generator()

    # Get the shuffle order
    order = stimList._playback_order

    for i in range(0,3):
        assert (playGen.next() == stims[order[i]].data).all()

def test_history(stim1, stim2, stim3):

    stims = [stim1, stim2, stim3]

    stimList = AudioStimPlaylist(stims, shuffle_playback=False)

    # Get the generator
    playGen = stimList.data_generator()

    # See if we can do looping sequential playback
    num_samples_played = 0
    for i in range(0,5):
        data = playGen.next()
        num_samples_played = num_samples_played + data.shape[0]

    assert(stimList.history == [0, 1, 2, 0, 1])

    assert([stimList.stims[i] for i in stimList.history] == [stim1, stim2, stim3, stim1, stim2])

    assert(stimList.num_samples_generated == num_samples_played)

def test_callbacks(stim1, stim2, stim3):
    stims = [stim1, stim2, stim3]

    my_callback_mock = mock.Mock()

    stimList = AudioStimPlaylist(stims, shuffle_playback=False, next_event_callbacks=my_callback_mock)

    data_gen = stimList.data_generator()

    data_gen.next()

    my_callback_mock.assert_called_with(stimList)

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

    data_gen.next()

    callback1.assert_called_once_with(s1)

    data_gen.next()

    callback1.assert_called_once_with(s1)
    callback2.assert_called_once_with(s2)
