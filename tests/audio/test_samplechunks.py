import pytest

import copy

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
