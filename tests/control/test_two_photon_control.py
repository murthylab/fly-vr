import pytest
from audio.stimuli import SinStim, AudioStimPlaylist
from control.two_photon_control import TwoPhotonController


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


def test_two_photon_control(stim1, stim2, stim3):
    stims = [stim1, stim2, stim3]
    stimList = AudioStimPlaylist(stims, shuffle_playback=False)


    two_photon_control = TwoPhotonController(start_channel_name="line0/port0",
                                             stop_channel_name="line0/por1",
                                             next_file_channel_name="line0/port2",
                                             audio_stim_playlist=stimList)

    playGen = stimList.data_generator()
    play2P = two_photon_control.data_generator()

    N = two_photon_control.SIGNAL_LENGTH

    next(playGen)
    data = next(play2P).data
    assert( (two_photon_control.start_signal[0:N, :] == data[0:N, :]).all() )

    next(playGen)
    data = next(play2P).data
    assert ((two_photon_control.next_signal[0:N, :] == data[0:N, :]).all())

    next(playGen)
    data = next(play2P).data
    assert ((two_photon_control.next_signal[0:N, :] == data[0:N, :]).all())

    next(playGen)
    data = next(play2P).data
    assert ((two_photon_control.next_signal[0:N, :] == data[0:N, :]).all())

def test_two_photon_no_sideeffects(stim1, stim2, stim3):
    stims = [stim1, stim2, stim3]
    stimList = AudioStimPlaylist(stims, shuffle_playback=False)

    two_photon_control = TwoPhotonController(start_channel_name="line0/port0",
                                             stop_channel_name="line0/por1",
                                             next_file_channel_name="line0/port2",
                                             audio_stim_playlist=stimList)

    playGen = stimList.data_generator()
    play2P = two_photon_control.data_generator()

    N = two_photon_control.SIGNAL_LENGTH

    next(playGen)
    data = next(play2P).data
    assert ((two_photon_control.start_signal[0:N, :] == data[0:N, :]).all())

    next(playGen)
    data = next(play2P).data
    assert ((two_photon_control.next_signal[0:N, :] == data[0:N, :]).all())

    # Now, recreate the generators, make sure there are no side effects.
    playGen = stimList.data_generator()
    play2P = two_photon_control.data_generator()

    next(playGen)
    data = next(play2P).data
    assert( (two_photon_control.start_signal[0:N, :] == data[0:N, :]).all() )

    next(playGen)
    data = next(play2P).data
    assert ((two_photon_control.next_signal[0:N, :] == data[0:N, :]).all())
