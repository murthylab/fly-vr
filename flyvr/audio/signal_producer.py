import uuid
import itertools
import abc
import copy

import numpy as np


class SampleChunk(object):
    """
    A class that encapsulated numpy arrays containing sample data along with metadata information. This allows us to
    record attributes like where the data was produced.
    """

    def __init__(self, data, producer_id):
        self.data = data
        self.producer_id = producer_id


class SignalProducer(object, metaclass=abc.ABCMeta):
    """
    A general class that abstracts away the key features of signal producers. Its main purpose is to provide a generator
    method interface and to keep track of the history of this generator's execution. AudioStimuli, AudioStimuluPlaylist,
    and others inherit from this class to standardize their interface.
    """

    # We want to keep track of every instance of a signal producer class. These instance IDs will be appended to their
    # event messages.
    instances_created = 0

    def __init__(self, dtype=np.float64):
        """
        Create a signal producer instance.

        :param dtype: The underlying data type for the numpy array that this class produces. float64 by default.
        """
        self.flyvr_shared_state = None
        self.backend = None

        # Use the number of instances created to set an ID for this instance
        self.producer_id = SignalProducer.instances_created

        # Increment the class shared number of instances created
        SignalProducer.instances_created += 1

        # Store dtype for this producer
        self.dtype = dtype

    def initialize(self, flyvr_shared_state, backend):
        self.flyvr_shared_state = flyvr_shared_state
        self.backend = backend

    @abc.abstractmethod
    def data_generator(self):
        """
        All signal producers need to define a data_generator() method that creates a generator iterator that produces
        the data when called.

        :return: A generator iterator that produces the signal data.
        """

    @property
    def num_channels(self):
        """
        How many channels the data chunks produced by this generator have.

        :return: The number of channels (or columns) in the data chunk.
        """
        data = next(self.data_generator()).data

        if data.ndim == 1:
            return 1
        else:
            return data.shape[1]

    @property
    def num_samples(self):
        """
        Get the number of samples produced by this signal producer for each call to its generator.

        :return: Number of samples for each data chunk.
        """
        data = next(self.data_generator()).data
        return data.shape[0]


def chunker(gen, chunk_size=100):
    """
    A function that takes a generator function that outputs arbitrary size SampleChunk objects. These object contain
    a numpy array of arbitrary size. This function can take SampleChunk objects and turn them into fix sized object or
    arbitrary size. It does this by creating a new generator that chunks the numpy array and appends the rest of the
    data and yields it.

    :param gen: A generator function that returns SampleChunk objects.
    :param chunk_size: The number of elements along the first dimension to include in each chunk.
    :return: A generator function that returns chunks.
    """
    next_chunk = None
    curr_data_sample = 0
    curr_chunk_sample = 0
    data = None
    num_samples = 0

    for i in itertools.count():

        if curr_data_sample == num_samples:
            sample_chunk_obj = next(gen)

            if sample_chunk_obj is None:
                yield None
                continue

            data = sample_chunk_obj.data
            curr_data_sample = 0
            num_samples = data.shape[0]

            # If this is our first chunk, use its dimensions to figure out the number of columns
            if next_chunk is None:
                chunk_shape = list(data.shape)
                chunk_shape[0] = chunk_size
                next_chunk = np.zeros(tuple(chunk_shape), dtype=data.dtype)

        # We want to add at most chunk_size samples to a chunk. We need to see if the current data will fit. If it does,
        # copy the whole thing. If it doesn't, just copy what will fit.
        sz = min(chunk_size - curr_chunk_sample, num_samples - curr_data_sample)
        if data.ndim == 1:
            next_chunk[curr_chunk_sample:(curr_chunk_sample + sz)] = data[curr_data_sample:(curr_data_sample + sz)]
        else:
            next_chunk[curr_chunk_sample:(curr_chunk_sample + sz), :] = data[curr_data_sample:(curr_data_sample + sz), :]

        curr_chunk_sample = curr_chunk_sample + sz
        curr_data_sample = curr_data_sample + sz

        if curr_chunk_sample == chunk_size:
            curr_chunk_sample = 0
            sample_chunk_obj = copy.copy(sample_chunk_obj)
            sample_chunk_obj.data = next_chunk.copy()
            yield sample_chunk_obj


class MixedSignal(SignalProducer):
    """
    The MixedSignal class is a simple class that takes a list of signal producer objects as it's input and combines them
    into one signal producer that generates a channel for each. Basically it combines data stored in different numpy
    arrays into a one array.
    """

    def __init__(self, signals, identifier=None):
        """
        Create the MixedSignal object that will combine these signals into one signal.

        :param signals: The list of signals to combine, one for each channel.
        """

        self.signals = signals

        # Check the dtypes of each producer to make sure they are compatible
        dtypes = [sig.dtype for sig in self.signals]

        dtype = dtypes[0]

        # Make sure all signals have the same dtype.
        if not all(typ == dtype for typ in dtypes):
            raise ValueError("Cannot created mixed signal from signals with different dtypes: %s" % (
                ', '.join('%s:%s' % (s.producer_id, s.dtype) for s in signals)))

        # Attach event next callbacks to this object, since it is a signal producer
        super(MixedSignal, self).__init__(dtype=dtype)

        # Grab a chunk from each generator to see how big their chunks are, we will need to make sure they are all the
        # same size later when we output a single chunk with multiple channels.
        data_gens = [signal.data_generator() for signal in self.signals]
        chunk_sizes = [next(gen).data.shape[0] for gen in data_gens]

        # Get the number of channels for each signal
        self.chunk_widths = []
        for gen in data_gens:
            chunk = next(gen).data
            if chunk.data.ndim == 1:
                self.chunk_widths.append(1)
            else:
                self.chunk_widths.append(chunk.data.shape[1])

        self.chunk_size = max(chunk_sizes)
        self.chunk_width = sum(self.chunk_widths)

        self._data = np.zeros((self.chunk_size, self.chunk_width), dtype=self.dtype)
        self._identifier = identifier or ('%s-%s' % (self.__class__.__name__, uuid.uuid4().hex))

    @property
    def identifier(self):
        return self._identifier

    def data_generator(self):
        """
        Create a data generator for this signal. Each signal passed to the constructor will be yielded as a separate
        column of the data chunk returned by this generator.

        :return: A generator that yields the combined signal SampleChunk(s)
        """

        # Intitialize data generators for these signals in the play list. Wrap each generator in a chunker with the same
        # size.
        data_gens = [chunker(signal.data_generator(), self.chunk_size) for signal in self.signals]

        while True:

            # Get the next set of chunks, one for each channel.
            chunks = [next(gen) for gen in data_gens]

            # Copy each chunk
            channel_idx = 0
            for i in range(len(chunks)):

                # This should not happen.
                assert chunks[i].data.shape[0] == self._data.shape[0]

                if chunks[i].data.ndim == 1:
                    self._data[:, channel_idx] = chunks[i].data
                else:
                    self._data[:, channel_idx:channel_idx + self.chunk_widths[i]] = chunks[i].data

                channel_idx = channel_idx + self.chunk_widths[i]

            # We are about to yield, send an event to our callbacks
            # self.trigger_next_callback(message_data=self.event_message, num_samples=self._data.shape[0])

            yield SampleChunk(data=self._data, producer_id=self.producer_id)


class ConstantSignal(SignalProducer):
    """
    A very simple signal that generates a constant value.
    """

    def __init__(self, constant, num_samples=1):
        # Attach event next callbacks to this object, since it is a signal producer
        super(ConstantSignal, self).__init__()

        self.constant = constant

        self.chunk = SampleChunk(data=np.ones(num_samples, dtype=self.dtype) * self.constant,
                                 producer_id=self.producer_id)

    def data_generator(self):
        while True:
            yield self.chunk


def data_generator_test(channels=1, num_samples=10000, dtype=np.float64):
    '''generator yields next chunk of data for output'''
    # generate all stimuli

    max_value = 5

    if dtype == np.uint8:
        max_value = 1

    data = list()
    for ii in range(2):
        # t = np.arange(0, 1, 1.0 / max(100.0 ** ii, 100))
        # tmp = np.tile(0.2 * np.sin(5000 * t).astype(np.float64), (channels, 1)).T

        # simple ON/OFF pattern
        tmp = max_value * ii * np.ones((channels, num_samples)).astype(dtype).T
        data.append(np.ascontiguousarray(tmp))  # `ascont...` necessary since `.T` messes up internal array format
    count = 0  # init counter
    try:
        while True:
            count += 1
            # print("{0}: generating {1}".format(count, data[(count-1) % len(data)].shape))
            yield SampleChunk(producer_id=0, data=data[(count - 1) % len(data)])
    except GeneratorExit:
        print("   cleaning up datagen.")
