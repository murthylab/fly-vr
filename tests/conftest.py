import pytest

from audio.sound_server import SoundServer


def _has_soundcard():
    # noinspection PyProtectedMember
    for _ in SoundServer._iter_compatible_output_devices(show_all=False):
        return True


def _has_daq(name=''):
    import ctypes
    import PyDAQmx as daq

    buff = ctypes.create_string_buffer(1024)
    # noinspection PyUnresolvedReferences
    daq.DAQmxGetSysDevNames(buff, 1024)
    c_str = buff.value.decode('ascii')
    devs = tuple(map(str.strip, c_str.split(',')))
    return (name in devs) if name else len(devs)


def pytest_collection_modifyitems(config, items):
    has_soundcard = _has_soundcard()
    has_daq = _has_daq()
    skip_no_soundcard = pytest.mark.skip(reason="no soundcard detected")
    skip_no_daq = pytest.mark.skip(reason="no daq detected")
    for item in items:
        if item.get_closest_marker('use_soundcard'):
            if not has_soundcard:
                item.add_marker(skip_no_soundcard)
        if item.get_closest_marker('use_daq'):
            if not has_daq:
                item.add_marker(skip_no_daq)
