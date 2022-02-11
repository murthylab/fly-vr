import pytest

import copy
import itertools

from flyvr.audio.stimuli import stimulus_factory, AudioStimPlaylist
from flyvr.audio.signal_producer import chunker, SampleChunk, chunk_producers_differ, SignalProducer


@pytest.fixture
def sinstim():
    # 1200 samples long
    return stimulus_factory(
        **{'name': 'sin', 'frequency': 10, 'amplitude': 2.0, 'duration': 100, 'pre_silence': 10, 'post_silence': 10,
           'sample_rate': 10000})


# 2400 samples long
_STIMPLAYLIST_PL = [
    {'_options': {'random_mode': 'shuffle', 'repeat': 2, 'random_seed': 42}},
    {'sin10hz': {'name': 'sin', 'frequency': 10, 'amplitude': 2.0, 'sample_rate': 10000,
                 'duration': 100, 'pre_silence': 10, 'post_silence': 10}},
    {'constant1': {'name': 'constant', 'amplitude': 1.0, 'sample_rate': 10000,
                   'duration': 100, 'pre_silence': 10, 'post_silence': 10}},
]


@pytest.fixture
def stimplaylist():
    # excuse the copy/deepcopy - because we also call this outside of the local scope
    # below, it would otherwise permute the global _STIMPLAYLIST_PL
    return AudioStimPlaylist.from_playlist_definition(copy.deepcopy(_STIMPLAYLIST_PL),
                                                      basedirs=[],
                                                      paused_fallback=False,
                                                      default_repeat=1)


def _chunk_uid(chunk: SampleChunk):
    return (chunk.producer_identifier,
            chunk.producer_instance_n,
            chunk.chunk_n,
            chunk.producer_playlist_n)


def test_single_stim_chunks(sinstim):
    stim = sinstim

    data_gen = stim.data_generator()
    c0 = next(data_gen)
    c1 = next(data_gen)
    c2 = next(data_gen)
    c3 = next(data_gen)

    ids = {_chunk_uid(c) for c in (c0, c1, c2, c3)}
    assert len(ids) == 1, 'chunk uids not all the same'

    assert c0.producer_identifier == stim.identifier
    assert c0.producer_instance_n == stim.producer_instance_n
    assert c0.chunk_n == -1
    assert c0.mixed_producer is False


def test_single_stim_chunker_chunks(sinstim):
    assert sinstim.data.shape == (1200, )

    gen = chunker(sinstim.data_generator(), 500)

    c0 = next(gen)
    assert c0.chunk_n == 0
    assert c0.producer_identifier == sinstim.identifier
    assert c0.producer_instance_n == sinstim.producer_instance_n
    assert c0.mixed_producer is False
    assert c0.producer_playlist_n == -1  # not from playlist

    c1 = next(gen)
    assert c1.chunk_n == 1
    assert c1.producer_identifier == sinstim.identifier
    assert c1.producer_instance_n == sinstim.producer_instance_n
    assert c1.mixed_producer is False
    assert c1.producer_playlist_n == -1

    c2 = next(gen)
    assert c2.chunk_n == 2
    assert c2.producer_identifier == sinstim.identifier
    assert c2.producer_instance_n == sinstim.producer_instance_n
    assert c2.mixed_producer is True
    assert c2.producer_playlist_n == -1

    assert chunk_producers_differ(c1, c2)

    c3 = next(gen)
    assert c3.chunk_n == 3
    assert c3.producer_identifier == sinstim.identifier
    assert c3.producer_instance_n == sinstim.producer_instance_n
    assert c3.mixed_producer is False
    assert c3.producer_playlist_n == -1

    assert not chunk_producers_differ(c2, c3)

    c4 = next(gen)
    assert c4.chunk_n == 4
    assert c4.producer_identifier == sinstim.identifier
    assert c4.producer_instance_n == sinstim.producer_instance_n
    assert c4.mixed_producer is True
    assert c4.producer_playlist_n == -1

    ids = {_chunk_uid(c) for c in (c0, c1, c2, c3, c4)}
    assert len(ids) == 5, 'chunk uids not all different'


def test_stim_playlist_random_order(monkeypatch):
    monkeypatch.setattr(SignalProducer, 'instances_created', 42)

    # grr can't call the fixture manually
    sp = AudioStimPlaylist.from_playlist_definition(copy.deepcopy(_STIMPLAYLIST_PL),
                                                    basedirs=[],
                                                    paused_fallback=False,
                                                    default_repeat=1)

    stims_in_order = [s for s in sp._iter_stims_with_randomization(True)]
    assert [s.identifier for s in stims_in_order] == ['constant1', 'sin10hz', 'constant1', 'sin10hz']

    # producer_instance_n is a 0-indexed count of how many playlist
    assert [s.producer_instance_n for s in stims_in_order] == [43, 42, 43, 42]


# noinspection DuplicatedCode
def test_stim_playlist_chunks(stimplaylist):

    # extract the underlying identifiers and instance_n for the stimulus items that
    # will be played.
    stims_in_order = [s for s in stimplaylist._iter_stims_with_randomization(True)]
    assert [s.identifier for s in stims_in_order] == ['constant1', 'sin10hz', 'constant1', 'sin10hz']

    sconstantid, ssind = stims_in_order[0].identifier, stims_in_order[1].identifier
    sconstantn, ssinn = stims_in_order[0].producer_instance_n, stims_in_order[1].producer_instance_n
    assert sconstantid == 'constant1'
    assert ssind == 'sin10hz'

    data_gen = stimplaylist.data_generator()
    c0 = next(data_gen)
    assert c0.chunk_n == -1
    assert c0.producer_identifier == sconstantid
    assert c0.producer_instance_n == sconstantn
    assert c0.mixed_producer is False

    c1 = next(data_gen)
    assert c1.chunk_n == -1
    assert c1.producer_identifier == ssind
    assert c1.producer_instance_n == ssinn
    assert c1.mixed_producer is False

    c2 = next(data_gen)
    assert c2.chunk_n == -1
    assert c2.producer_identifier == sconstantid
    assert c2.producer_instance_n == sconstantn
    assert c2.mixed_producer is False

    c3 = next(data_gen)
    assert c3.chunk_n == -1
    assert c3.producer_identifier == ssind
    assert c3.producer_instance_n == ssinn
    assert c3.mixed_producer is False

    ids = {_chunk_uid(c) for c in (c0, c1, c2, c3)}
    assert len(ids) == 4

    c4 = next(data_gen)
    assert c4 is None


# noinspection DuplicatedCode
def test_stim_playlist_chunker_chunks_1000(stimplaylist):

    # extract the underlying identifiers and instance_n for the stimulus items that
    # will be played.
    stims_in_order = [s for s in stimplaylist._iter_stims_with_randomization(True)]
    assert [s.identifier for s in stims_in_order] == ['constant1', 'sin10hz', 'constant1', 'sin10hz']

    sconstantid, ssind = stims_in_order[0].identifier, stims_in_order[1].identifier
    sconstantn, ssinn = stims_in_order[0].producer_instance_n, stims_in_order[1].producer_instance_n
    assert sconstantid == 'constant1'
    assert ssind == 'sin10hz'

    # a chunk length of 1000 for stims of 1200 does not break evenly, so we get some mixed chunks
    gen = chunker(stimplaylist.data_generator(), 1000)

    c0 = next(gen)
    assert c0.chunk_n == 0
    assert c0.producer_playlist_n == 0
    assert c0.producer_identifier == sconstantid
    assert c0.producer_instance_n == sconstantn
    assert c0.mixed_producer is False

    assert chunk_producers_differ(None, c0)

    c1 = next(gen)
    assert c1.chunk_n == 1
    assert c1.producer_playlist_n == 1
    assert c1.producer_identifier == ssind
    assert c1.producer_instance_n == ssinn
    assert c1.mixed_producer is True
    assert c1.mixed_start_offset == 200

    assert chunk_producers_differ(c0, c1)

    c2 = next(gen)
    assert c2.chunk_n == 2
    assert c2.producer_playlist_n == 2
    assert c2.producer_identifier == sconstantid  # i.e. play the constant1 again
    assert c2.producer_instance_n == sconstantn
    assert c2.mixed_producer is True
    assert c2.mixed_start_offset == 400

    assert chunk_producers_differ(c1, c2)

    c3 = next(gen)
    assert c3.chunk_n == 3
    assert c3.producer_playlist_n == 3
    assert c3.producer_identifier == ssind  # i.e. play the sin10hz again
    assert c3.producer_instance_n == ssinn
    assert c3.mixed_producer is True
    assert c3.mixed_start_offset == 600

    assert chunk_producers_differ(c2, c3)

    # because the chunk can't evenly fill the buffer size
    c4 = next(gen)
    assert c4 is None


# noinspection DuplicatedCode
def test_stim_playlist_chunker_chunks_same_sized(stimplaylist):

    # extract the underlying identifiers and instance_n for the stimulus items that
    # will be played.
    stims_in_order = [s for s in stimplaylist._iter_stims_with_randomization(True)]
    assert [s.identifier for s in stims_in_order] == ['constant1', 'sin10hz', 'constant1', 'sin10hz']

    sconstantid, ssind = stims_in_order[0].identifier, stims_in_order[1].identifier
    sconstantn, ssinn = stims_in_order[0].producer_instance_n, stims_in_order[1].producer_instance_n
    assert sconstantid == 'constant1'
    assert ssind == 'sin10hz'

    # chunker is same size as stim, so no mixng, but still check
    # chunk_producers_differ does the right thing
    gen = chunker(stimplaylist.data_generator(), 1200)

    c0 = next(gen)
    assert c0.chunk_n == 0
    assert c0.producer_identifier == sconstantid
    assert c0.producer_instance_n == sconstantn
    assert c0.mixed_producer is False

    assert chunk_producers_differ(None, c0)

    c1 = next(gen)
    assert c1.chunk_n == 1
    assert c1.producer_identifier == ssind
    assert c1.producer_instance_n == ssinn
    assert c1.mixed_producer is False

    assert chunk_producers_differ(c0, c1)

    c2 = next(gen)
    assert c2.chunk_n == 2
    assert c2.producer_identifier == sconstantid
    assert c2.producer_instance_n == sconstantn
    assert c2.mixed_producer is False

    assert chunk_producers_differ(c1, c2)


@pytest.mark.parametrize('chunksize', [100, 500, 1000, 1200])
def test_stim_playlist_chunker_chunks_for_csv_explanation(monkeypatch, chunksize, tmpdir):
    import pandas as pd

    # reset the produce_instance to 0
    monkeypatch.setattr(SignalProducer, 'instances_created', 0)

    stimplaylist = AudioStimPlaylist.from_playlist_definition(copy.deepcopy(_STIMPLAYLIST_PL),
                                                              basedirs=[],
                                                              paused_fallback=False,
                                                              default_repeat=1)

    gen = chunker(stimplaylist.data_generator(), chunksize)

    recs = []
    for i, chunk in enumerate(gen):
        if chunk is None:
            break

        recs.append({'sample_id': i,
                     'sample': (i + 1) * chunksize,
                     'producer_identifier': chunk.producer_identifier,
                     'producer_instance_n': chunk.producer_instance_n,
                     'producer_playlist_n': chunk.producer_playlist_n,
                     'chunk_n': chunk.chunk_n,
                     'mixed_producer': chunk.mixed_producer,
                     'mixed_start_offset': chunk.mixed_start_offset})

    _path = tmpdir.join('%d.csv' % chunksize).strpath
    pd.DataFrame(recs).to_csv(_path, index=False)

    print(_path)

def test_play_item_produces_new_instance_chunk(stimplaylist):
    # test new data generator instance
    a = stimplaylist.play_item('sin10hz')
    b = stimplaylist.play_item('constant1')
    assert a != b
    assert hash(a) != hash(b)
    c = stimplaylist.play_item('sin10hz')
    assert a != c
    assert hash(a) != hash(c)

    # next() on an individual AudioStim without a chunker will just return the entire
    # array in a loop, aka from the same chunk producer
    ca0 = next(a)
    assert ca0.producer_identifier == 'sin10hz'
    assert ca0.producer_playlist_n == 0
    assert ca0.data.shape == (1200,)
    ca1 = next(a)
    assert ca1.data.shape == (1200,)
    assert ca1.producer_identifier == 'sin10hz'
    assert ca1.producer_playlist_n == 0
    assert not chunk_producers_differ(ca0, ca1)
    ca2 = next(a)
    assert ca2.data.shape == (1200,)
    assert ca2.producer_identifier == 'sin10hz'
    assert ca2.producer_playlist_n == 0
    assert not chunk_producers_differ(ca0, ca2)

    # first chunk on different AudioStim from the previous play_item
    cb0 = next(b)
    assert cb0.data.shape == (1200,)
    assert cb0.producer_identifier == 'constant1'
    assert cb0.producer_playlist_n == 1
    assert chunk_producers_differ(ca0, cb0)

    # first chunk on same AudioStim from the first sin10hz
    cc0 = next(c)
    assert cc0.data.shape == (1200,)
    assert cc0.producer_identifier == 'sin10hz'
    assert cc0.producer_playlist_n == 0
    assert chunk_producers_differ(ca0, cc0)


def test_play_item_produces_new_instance_chunk_chunker(stimplaylist):
    a = chunker(stimplaylist.play_item('sin10hz'), 600)
    b = chunker(stimplaylist.play_item('constant1'), 600)
    c = chunker(stimplaylist.play_item('sin10hz'), 600)

    ca0 = next(a)
    assert ca0.producer_identifier == 'sin10hz'
    assert ca0.producer_playlist_n == 0
    assert ca0.data.shape == (600,)
    ca1 = next(a)
    assert ca1.producer_identifier == 'sin10hz'
    assert ca1.producer_playlist_n == 0
    assert ca1.data.shape == (600,)
    assert not chunk_producers_differ(ca0, ca1)
    # loops back round to the start
    ca2 = next(a)
    assert ca2.producer_identifier == 'sin10hz'
    assert ca2.producer_playlist_n == 0
    assert ca2.data.shape == (600,)
    assert not chunk_producers_differ(ca1, ca2)
    assert not chunk_producers_differ(ca0, ca2)

    cb0 = next(b)
    assert cb0.producer_identifier == 'constant1'
    assert cb0.producer_playlist_n == 1
    assert cb0.data.shape == (600,)

    assert chunk_producers_differ(ca0, cb0)
    assert chunk_producers_differ(ca2, cb0)

    cc0 = next(c)
    assert cc0.producer_identifier == 'sin10hz'
    assert cc0.producer_playlist_n == 0
    assert cc0.data.shape == (600,)
    cc1 = next(c)
    assert cc1.producer_identifier == 'sin10hz'
    assert cc1.producer_playlist_n == 0
    assert cc1.data.shape == (600,)
    assert not chunk_producers_differ(cc0, cc1)
    # loops back round to the start
    cc2 = next(c)
    assert cc2.producer_identifier == 'sin10hz'
    assert cc2.producer_playlist_n == 0
    assert cc2.data.shape == (600,)
    assert not chunk_producers_differ(cc1, cc2)
    assert not chunk_producers_differ(cc0, cc2)

    # all chunks on same AudioStim differ
    for a,c in itertools.product((ca0,ca1,ca2), (cc0,cc1,cc2)):
        chunk_producers_differ(a, c)

