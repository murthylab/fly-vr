import pytest

from audio.sound_server import SoundServer
from audio.stimuli import SinStim


@pytest.mark.use_soundcard
def test_list_devices():
    from io import StringIO
    s = StringIO()
    SoundServer.list_supported_asio_output_devices(out=s)
    assert 'ASIO' in s.getvalue()


@pytest.mark.use_soundcard
def test_play_sin(tmpdir):
    import time
    import h5py

    from common import SharedState
    from common.logger import DatasetLogServer

    CHUNK_SIZE = 128
    stim1 = SinStim(frequency=200, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)

    dest = tmpdir.join('test.h5').strpath

    log_server = DatasetLogServer()
    logger = log_server.start_logging_server(dest)

    shared_state = SharedState(None, logger)

    sound_server = SoundServer(flyvr_shared_state=shared_state)
    sound_client = sound_server.start_stream(frames_per_buffer=CHUNK_SIZE, suggested_output_latency=0.002)
    sound_client.play(stim1)
    time.sleep(1.5)

    sound_client.close()
    log_server.stop_logging_server()
    log_server.wait_till_close()

    with h5py.File(dest) as h5:
        assert '/fictrac/soundcard_synchronization_info' in h5