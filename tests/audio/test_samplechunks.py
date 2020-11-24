import pytest

from flyvr.audio.stimuli import stimulus_factory, AudioStimPlaylist
from flyvr.audio.signal_producer import chunker, SampleChunk, chunk_producers_differ


@pytest.fixture
def sinstim():
    # 1200 samples long
    return stimulus_factory(
        **{'name': 'sin', 'frequency': 10, 'amplitude': 2.0, 'duration': 100, 'pre_silence': 10, 'post_silence': 10,
           'sample_rate': 10000})


@pytest.fixture
def stimplaylist():
    # 2400 samples long
    pl = [
        {'_options': {'random_mode': 'shuffle', 'repeat': 2, 'random_seed': 42}},
        {'sin10hz': {'name': 'sin', 'frequency': 10, 'amplitude': 2.0, 'sample_rate': 10000,
                     'duration': 100, 'pre_silence': 10, 'post_silence': 10}},
        {'constant1': {'name': 'constant', 'amplitude': 1.0, 'sample_rate': 10000,
                       'duration': 100, 'pre_silence': 10, 'post_silence': 10}},
    ]
    return AudioStimPlaylist.from_playlist_definition(pl,
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

    c1 = next(gen)
    assert c1.chunk_n == 1
    assert c1.producer_identifier == sinstim.identifier
    assert c1.producer_instance_n == sinstim.producer_instance_n
    assert c1.mixed_producer is False

    c2 = next(gen)
    assert c2.chunk_n == 2
    assert c2.producer_identifier == sinstim.identifier
    assert c2.producer_instance_n == sinstim.producer_instance_n
    assert c2.mixed_producer is True

    assert chunk_producers_differ(c1, c2)

    c3 = next(gen)
    assert c3.chunk_n == 3
    assert c3.producer_identifier == sinstim.identifier
    assert c3.producer_instance_n == sinstim.producer_instance_n
    assert c3.mixed_producer is False

    assert not chunk_producers_differ(c2, c3)

    c4 = next(gen)
    assert c4.chunk_n == 4
    assert c4.producer_identifier == sinstim.identifier
    assert c4.producer_instance_n == sinstim.producer_instance_n
    assert c4.mixed_producer is True

    ids = {_chunk_uid(c) for c in (c0, c1, c2, c3, c4)}
    assert len(ids) == 5, 'chunk uids not all different'


# noinspection DuplicatedCode
def test_stim_playlist_chunks(stimplaylist):

    # the ::-1 is to reverse the list returned by the dumb iter here as compared
    # to the true {'_options': {'random_mode': 'shuffle', 'repeat': 2, 'random_seed': 42}} playlist
    # order which happens to with this seed, return things in the other order
    sconstantid, ssind = [s.identifier for s in stimplaylist][::-1]
    sconstantn, ssinn = [s.producer_instance_n for s in stimplaylist][::-1]

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


def test_stim_playlist_chunker_chunks(stimplaylist):
    # see comment in previous function
    sconstantid, ssind = [s.identifier for s in stimplaylist][::-1]
    sconstantn, ssinn = [s.producer_instance_n for s in stimplaylist][::-1]

    gen = chunker(stimplaylist.data_generator(), 1000)

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
    assert c1.mixed_producer is True
    assert c1.mixed_start_offset == 200

    assert chunk_producers_differ(c0, c1)

    c2 = next(gen)
    assert c2.chunk_n == 2
    assert c2.producer_identifier == sconstantid
    assert c2.producer_instance_n == sconstantn
    assert c2.mixed_producer is True
    assert c2.mixed_start_offset == 400

    c3 = next(gen)
    assert c3.chunk_n == 3
    assert c3.producer_identifier == ssind
    assert c3.producer_instance_n == ssinn
    assert c3.mixed_producer is True
    assert c3.mixed_start_offset == 600

    c4 = next(gen)
    assert c4 is None


def test_stim_playlist_chunker_chunks_same_sized(stimplaylist):
    # see comment in previous function
    sconstantid, ssind = [s.identifier for s in stimplaylist][::-1]
    sconstantn, ssinn = [s.producer_instance_n for s in stimplaylist][::-1]

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
