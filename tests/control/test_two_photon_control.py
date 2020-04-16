import pytest

from flyvr.audio.stimuli import SinStim, AudioStimPlaylist
from flyvr.audio.io_task import IOTask, DAQ_NUM_OUTPUT_SAMPLES, DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT
from flyvr.control.two_photon_control import TwoPhotonController
from flyvr.common import SharedState
from flyvr.common.logger import DatasetLogServer


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


@pytest.mark.use_daq
def test_io_a_output(tmpdir):
    import time

    import h5py

    with DatasetLogServer() as log_server:

        shared_state = SharedState(None, logger=log_server.start_logging_server(tmpdir.join('test.h5').strpath))

        taskAO = IOTask(cha_name=['ao1'], cha_type="output",
                        num_samples_per_chan=DAQ_NUM_OUTPUT_SAMPLES,
                        num_samples_per_event=DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT,
                        shared_state=shared_state)

        taskAO.StartTask()
        for i in range(10):
            time.sleep(0.1)

        taskAO.StopTask()
        taskAO.stop()
        taskAO.ClearTask()

    with h5py.File(shared_state.logger.log_filename, mode='r') as h5:
        assert h5['fictrac']['daq_synchronization_info'].shape[-1] == 2  # 2 columns
