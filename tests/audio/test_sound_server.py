import pytest

from audio.sound_server import SoundServer


@pytest.mark.use_soundcard
def test_list_devices():
    from io import StringIO
    s = StringIO()
    SoundServer.list_supported_asio_output_devices(out=s)
    assert 'ASIO' in s.getvalue()

