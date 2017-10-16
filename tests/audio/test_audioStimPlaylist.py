import pytest
import math

from audio.stimuli import SinStim, AudioStimPlaylist

def test_generator():
    stim1 = SinStim(230, 2.0, 0.0, 40000, 200, 0, 0)
    stim2 = SinStim(330, 2.0, 0.0, 40000, 200, 0, 0)
    stim3 = SinStim(430, 2.0, 0.0, 40000, 200, 0, 0)
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