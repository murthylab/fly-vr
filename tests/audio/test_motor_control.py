from flyvr.audio.signal_producer import MixedSignal
from flyvr.audio.stimuli import SinStim, AudioStimPlaylist
from flyvr.control.two_photon_control import TwoPhotonController


def test_mixed_control():
    stim1 = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    stim2 = SinStim(frequency=430, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    stimList = AudioStimPlaylist([stim1, stim2], shuffle_playback=False)

    two_photon_controller = TwoPhotonController(start_channel_name="",
                                                stop_channel_name="",
                                                next_file_channel_name="",
                                                audio_stim_playlist=stimList)

    mixed = MixedSignal([two_photon_controller])

    gen = mixed.data_generator()

    chunk = next(gen).data

    assert(chunk.shape[1] == 5)