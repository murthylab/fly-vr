import numpy as np
import math

from audio.stimuli import SinStim
from audio.signal_producer import SampleChunk, SignalProducer, MixedSignal, chunker, ConstantSignal


def check_chunker(test_gen, chunk_size):
    # Get a generator iterator
    data_gen_iter = test_gen()

    # Run the data iterator 10 times to get some data. Put it
    # all in one array.
    num_data_to_test = 10
    test_data = next(data_gen_iter).data
    for i in range(num_data_to_test - 1):
        test_data = np.concatenate((test_data, next(data_gen_iter).data), axis=0)

    # Reset generator
    data_gen_iter = test_gen()

    # Make a chunk generator iterator out of it
    chunk_gen = chunker(data_gen_iter, chunk_size)

    # Now walk the chunk generator enough to get enough chunks to compare to
    # test data that we generated above
    num_chunks = int(math.ceil(float(test_data.shape[0]) / float(chunk_size)))
    chunk_test_data = next(chunk_gen).data
    for i in range(num_chunks - 1):
        chunk_test_data = np.concatenate((chunk_test_data, next(chunk_gen).data), axis=0)

    # Truncate the data since the chunk size will probably not be a factor
    # of test data size.
    if test_data.ndim == 1:
        chunk_test_data = chunk_test_data[0:test_data.shape[0]]
    elif test_data.ndim == 2:
        chunk_test_data = chunk_test_data[0:test_data.shape[0], :]

    # Compare the data, make sure it is equal
    assert ((chunk_test_data == test_data).all())


def test_chunker():

    def simple_gen():
        x = 0
        while True:
            yield SampleChunk(data=np.arange(x, x + 51), producer_id=1)
            x = x + 51

    # Test out the chunker on a very simple generator
    check_chunker(simple_gen, 100)
    check_chunker(simple_gen, 101)
    check_chunker(simple_gen, 1)

    # Now test out the generator on a stimulus audio generator, try it when the chunks are
    # actually bigger than the generators data chunk size.
    stim = SinStim(230, 2.0, 0.0, 40000, 200, 1.0, 0, 0)
    check_chunker(stim.data_generator, 10000)
    check_chunker(stim.data_generator, 10551)

def test_mixed_signal():
    stim1 = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    stim2 = SinStim(frequency=330, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    mixed = MixedSignal([stim1, stim2])

    gen = mixed.data_generator()

    chunk = next(gen)

    # Make sure the mixed signal has two channels
    assert(chunk.data.shape[1] == 2)

    # Make sure each channel has the correct data.
    assert(np.array_equal(chunk.data[:,0], stim1.data))
    assert(np.array_equal(chunk.data[:,1], stim2.data))

def test_mixed_signal_chunked():

    stim1 = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    stim2 = SinStim(frequency=330, amplitude=2.0, phase=0.0, sample_rate=40000,
                   duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                   attenuator=None)
    mixed = MixedSignal([stim1, stim2])

    check_chunker(mixed.data_generator, 128)

def test_constant_signal():

    constant = 5.0

    stim = ConstantSignal(constant)
    gen = stim.data_generator()

    for i in range(100):
        assert(np.array_equal(next(gen).data, np.array([constant])))

    check_chunker(stim.data_generator, 100)


def test_mix_different_sizes():

    # Create two signals, the chunks their generators yield will be different sizes.
    stim1 = SinStim(frequency=230, amplitude=2.0, phase=0.0, sample_rate=40000,
                    duration=200, intensity=1.0, pre_silence=0, post_silence=0,
                    attenuator=None)
    stim2 = ConstantSignal(5)

    mixed = MixedSignal([stim1, stim2])

    gen = mixed.data_generator()

    for i in range(500):
        chunk = next(gen).data
        assert(np.array_equal(chunk[:,0], stim1.data))
        assert(np.array_equal(chunk[:,1], np.ones(shape=stim1.data.shape)*5))
