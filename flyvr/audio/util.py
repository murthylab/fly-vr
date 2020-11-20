import os.path

import matplotlib.pyplot as plt

from flyvr.common import Randomizer
from flyvr.audio.stimuli import AudioStimPlaylist


def get_paylist_object(options, playlist_type, paused_fallback, default_repeat, attenuator):
    stim_playlist = options.playlist.get(playlist_type)

    basedirs = [os.getcwd()]
    if getattr(options, '_config_file_path'):
        # noinspection PyProtectedMember
        basedirs.insert(0, os.path.dirname(options._config_file_path))

    playlist_object = None
    if stim_playlist:
        playlist_object = AudioStimPlaylist.from_playlist_definition(stim_playlist,
                                                                     basedirs=basedirs,
                                                                     paused_fallback=paused_fallback,
                                                                     default_repeat=default_repeat,
                                                                     attenuator=attenuator)

    return playlist_object, basedirs


def plot_playlist(options, playlist_type):
    pl, _ = get_paylist_object(options, playlist_type,
                               paused_fallback=False, default_repeat=1, attenuator=None)
    # noinspection PyProtectedMember
    plt.plot(pl._to_array(fix_repeat_forver=True))
    plt.show()

