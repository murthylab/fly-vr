import pytest
import math
import numpy as np

from audio.io_task import chunker
from audio.stimuli import SinStim

def check_chunker(test_gen, chunk_size):
    # Get a generator iterator
    data_gen_iter = test_gen()

    # Run the data iterator 10 times to get some data. Put it
    # all in one array.
    num_data_to_test = 10
    test_data = data_gen_iter.next()
    for i in range(num_data_to_test - 1):
        test_data = np.concatenate((test_data, data_gen_iter.next()), axis=0)

    # Reset generator
    data_gen_iter = test_gen()

    # Make a chunk generator iterator out of it
    chunk_gen = chunker(data_gen_iter, chunk_size)

    # Now walk the chunk generator enough to get enough chunks to compare to
    # test data that we generated above
    num_chunks = int(math.ceil(float(test_data.shape[0]) / float(chunk_size)))
    chunk_test_data = chunk_gen.next()
    for i in range(num_chunks - 1):
        chunk_test_data = np.concatenate((chunk_test_data, chunk_gen.next()), axis=0)

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
            yield np.arange(x, x + 51)
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



