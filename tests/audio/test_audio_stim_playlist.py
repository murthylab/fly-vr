import pytest
import yaml

import numpy as np

from flyvr.common import Randomizer
from flyvr.audio.signal_producer import chunker
from flyvr.audio.stimuli import SinStim, AudioStimPlaylist
from flyvr.audio.stimuli import legacy_factory


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


def test_generator(stim1, stim2, stim3):
    stims = (stim1, stim2, stim3)

    stimList = AudioStimPlaylist(stims,
                                 random=Randomizer(*[s.identifier for s in stims], mode=Randomizer.MODE_NONE,
                                                   repeat=100))

    # Get the generator
    playGen = stimList.data_generator()

    # See if we can do looping sequential playback
    for i in range(0, 5):
        assert (next(playGen).data == stims[i % 3].data).all()

    rs = 42

    # Now lets check if shuffle is working. Make sure no stimulus is repeating.
    stimList = AudioStimPlaylist(stims,
                                 random=Randomizer(*[s.identifier for s in stims],
                                                   mode=Randomizer.MODE_SHUFFLE_NON_REPEAT,
                                                   repeat=2, random_seed=rs))
    # Get the generator
    playGen = stimList.data_generator()

    # Get the shuffle order, use the same seed as the playlist
    rng = np.random.RandomState(seed=rs)

    stims = list(stims)
    rng.shuffle(stims)

    for s in stims:
        assert (next(playGen).data == s.data).all()

    rng.shuffle(stims)

    for s in stims:
        assert (next(playGen).data == s.data).all()


def test_legacy_multi_channel_playlist(tmpdir):
    import os.path

    PATH = 'tests/test_data/opto_control_playlist.txt'

    stimList = AudioStimPlaylist.from_legacy_filename(PATH)
    gen = chunker(stimList.data_generator(), 1000)
    chunk = next(gen).data
    assert (chunk.shape[1] == 4)
    assert (stimList.num_channels == 4)

    with pytest.raises(IOError):
        with open(PATH, 'rt') as f:
            legacy_factory(f.readlines()[1:],
                           basedirs=[tmpdir.strpath])

    with open(PATH, 'rt') as f:
        stims = legacy_factory(f.readlines()[1:],
                               basedirs=[os.path.dirname(PATH)])

    stimList = AudioStimPlaylist(stims)
    gen = chunker(stimList.data_generator(), 1000)
    chunk = next(gen).data
    assert (chunk.shape[1] == 4)
    assert (stimList.num_channels == 4)


def test_no_side_effects(stim1, stim2, stim3):
    stims = [stim1, stim2, stim3]

    stimList = AudioStimPlaylist(stims,
                                 random=Randomizer(*[s.identifier for s in stims], mode=Randomizer.MODE_NONE,
                                                   repeat=4))

    # Get the generator
    playGen = stimList.data_generator()

    # See if we can do looping sequential playback
    for i in range(6):
        assert (next(playGen).data == stims[i % 3].data).all()

    # Setting shuffle on the original object, should have no effect on the previously created generator
    stimList.shuffle_playback = True

    # See if we can do looping sequential playback
    for i in range(6):
        assert (next(playGen).data == stims[i % 3].data).all()

    with pytest.raises(AttributeError):
        # playlist repeats exhaused
        _ = next(playGen).data


def test_legacy_opto_parts():
    # a complicated way to make a 60s period of 0 output
    l = 'silentStim_TDUR4s	10000	1	30000	26000	0	5	250'

    st = legacy_factory([l], basedirs=['tests/test_data/nivedita_vr1/'])[0]
    assert st is not None
    desc = st.describe()
    assert desc['sample_rate'] == 10000
    arr = st.data
    assert arr.shape == (int((30 + 4 + 26) * desc['sample_rate']), )
    assert arr.shape == (600000, )
    assert arr.max() == 0.0
    assert arr.min() == 0.0

    l = '190712_opto_10sON_90sOFF	10000	1	5000	5000	0	9	-1'
    st = legacy_factory([l], basedirs=['tests/test_data/nivedita_vr1/'])[0]
    assert st is not None
    desc = st.describe()
    assert desc['pre_silence'] == 5000
    assert desc['post_silence'] == 5000
    assert desc['sample_rate'] == 10000
    arr = st.data
    assert arr.shape == (int((5 + 100 + 5) * desc['sample_rate']), )
    assert arr.max() == 9.0
    assert arr.min() == 0.0


def test_legacy_opto_parts_multiple():
    lines = ('silentStim_TDUR4s	10000	1	30000	26000	0	5	250',
             '190712_opto_10sON_90sOFF	10000	1	5000	5000	0	9	-1')
    stims = legacy_factory(lines, basedirs=['tests/test_data/nivedita_vr1/'])
    ap = AudioStimPlaylist(stims)
    arr = ap._to_array()
    # these are seconds durations - see two tests above
    assert arr.shape == (int((5 + 100 + 5 + 30 + 4 + 26) * 10000), )


def test_legacy_opto_convert():
    pl = AudioStimPlaylist.from_legacy_filename('tests/test_data/nivedita_vr1/opto_nivamasan_10sON90sOFF.txt')
    arr = pl._to_array()
    assert arr.shape == (17100000, )


def test_opto_convert_manual():
    pl1 = AudioStimPlaylist.from_legacy_filename('tests/test_data/nivedita_vr1/opto_nivamasan_10sON90sOFF.txt')
    arr1 = pl1._to_array()
    assert arr1.shape == (17100000, )

    def _from_yaml(_path):
        with open(_path) as f:
            conf = yaml.load(f)

        return AudioStimPlaylist.from_playlist_definition(conf['playlist']['audio'],
                                                          basedirs=['tests/test_data/nivedita_vr1/'],
                                                          paused_fallback=False,
                                                          default_repeat=1)

    # manual conversion
    pl2 = _from_yaml('tests/test_data/nivedita_vr1/opto_nivamasan_10sON90sOFF.yml')
    arr2 = pl2._to_array(fix_repeat_forver=False)
    assert arr2.shape == (17100000, )
    np.testing.assert_equal(arr1, arr2)

    # auto conversion
    pl3 = _from_yaml('tests/test_data/nivedita_vr1/opto_nivamasan_10sON90sOFF.txt.yml')
    arr3 = pl3._to_array(fix_repeat_forver=False)
    np.testing.assert_equal(arr2, arr3)
