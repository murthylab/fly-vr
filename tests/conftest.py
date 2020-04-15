import pytest

from audio.sound_server import SoundServer


def _has_soundcard():
    # noinspection PyProtectedMember
    for _ in SoundServer._iter_compatible_output_devices(show_all=False):
        return True


def pytest_collection_modifyitems(config, items):
    has_soundcard = _has_soundcard()
    skip_no_soundcard = pytest.mark.skip(reason="no soundcard detected")
    for item in items:
        if item.get_closest_marker('use_soundcard'):
            if not has_soundcard:
                item.add_marker(skip_no_soundcard)
