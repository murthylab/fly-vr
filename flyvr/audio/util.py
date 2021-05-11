import os.path

import matplotlib.pyplot as plt

from flyvr.common import Randomizer
from flyvr.audio.stimuli import AudioStimPlaylist


def get_paylist_object(options, playlist_type, paused_fallback, default_repeat, attenuator, _extra_playlist_path=None):
    stim_playlist = options.playlist.get(playlist_type)

    basedirs = [os.getcwd()]
    if getattr(options, '_config_file_path'):
        # noinspection PyProtectedMember
        basedirs.insert(0, os.path.dirname(options._config_file_path))
    if _extra_playlist_path is not None:
        basedirs.insert(0, os.path.abspath(_extra_playlist_path))

    playlist_object = None
    if stim_playlist:
        playlist_object = AudioStimPlaylist.from_playlist_definition(stim_playlist,
                                                                     basedirs=basedirs,
                                                                     paused_fallback=paused_fallback,
                                                                     default_repeat=default_repeat,
                                                                     attenuator=attenuator)

    return playlist_object, basedirs


def plot_playlist(options, playlist_type, show_plot=True, _extra_playlist_path=None):
    pl, _ = get_paylist_object(options, playlist_type,
                               paused_fallback=False, default_repeat=1, attenuator=None,
                               _extra_playlist_path=_extra_playlist_path)
    # noinspection PyProtectedMember
    plt.plot(pl._to_array(fix_repeat_forver=True))
    if show_plot:
        plt.show()

