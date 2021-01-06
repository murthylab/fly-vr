import abc
import copy

from typing import Optional, Callable, Iterator

import numpy as np


class SampleChunk(object):
    """
    A class that encapsulated numpy arrays containing sample data along with metadata information
    about where it was produced.
    """
    SYNCHRONIZATION_INFO_FIELDS = ('fictrac_frame_num',
                                   'daq_output_num_samples_written',
                                   'daq_input_num_samples_read',
                                   'sound_output_num_samples_written',
                                   'video_output_num_frames',
                                   'producer_instance_n', 'chunk_n', 'producer_playlist_n',
                                   'mixed_producer', 'mixed_start_offset')
    SYNCHRONIZATION_INFO_NUM_FIELDS = len(SYNCHRONIZATION_INFO_FIELDS)

    __slots__ = ["data", "producer_identifier", "producer_instance_n", "chunk_n", "producer_playlist_n",
                 "mixed_producer", "mixed_start_offset"]

    def __init__(self, data, producer_identifier, producer_instance_n, chunk_n=-1, producer_playlist_n=-1,
                 mixed_producer=False, mixed_start_offset=0):
        self.data = data
        self.producer_identifier = producer_identifier
        self.producer_instance_n = producer_instance_n
        self.chunk_n = chunk_n
        self.producer_playlist_n = producer_playlist_n
        self.mixed_producer = mixed_producer
        self.mixed_start_offset = mixed_start_offset

    def __repr__(self):
        if self.mixed_producer:
            return "<SampleChunk([MIXED ... %s(offset=%d)], chunk_n=%d, shape=%r)>" % (
                self.producer_identifier, self.mixed_start_offset, self.chunk_n, self.data.shape)

        extra = []
        if self.chunk_n != -1:
            extra.append('chunk_n=%d' % self.chunk_n)
        if self.producer_playlist_n != -1:
            extra.append('playlist_n=%d' % self.producer_playlist_n)

        if extra:
            extra = (', '.join(extra)) + ', '
        else:
            extra = ''

        return "<SampleChunk(%s, n=%s, %sshape=%r)>" % (self.producer_identifier, self.producer_instance_n, extra,
                                                        self.data.shape)

    @classmethod
    def new_silence(cls, data):
        return cls(data,
                   producer_identifier='_silence', producer_instance_n=-1)


def chunk_producers_differ(prev: Optional[SampleChunk], this: Optional[SampleChunk]):
    if (prev is not None) and (this is not None):
        return this.mixed_producer or (prev.producer_identifier,
                                       prev.producer_playlist_n) != (this.producer_identifier,
                                                                     this.producer_playlist_n)
    elif (prev is None) and (this is not None):
        return True
    else:
        # handles either non-None
        return prev == this


CallbackFunction = Callable[[SampleChunk], None]


class SignalProducer(object, metaclass=abc.ABCMeta):
    """
    A general class that abstracts away the key features of signal producers. Its main purpose is to provide a generator
    method interface and to keep track of the history of this generator's execution. AudioStimuli, AudioStimuluPlaylist,
    and others inherit from this class to standardize their interface.
    """

    # keep track of every instance of a signal producer class.
    instances_created = 0

    SUPPORTED_DTYPES = np.float64,

    def __init__(self, type_, instance_identifier,
                 next_event_callback: Optional[CallbackFunction] = None):

        self.backend = None

        self.producer_instance_n = SignalProducer.instances_created
        SignalProducer.instances_created += 1

        self.type = type_
        self.identifier = instance_identifier
        self.dtype = np.float64

        self._next_event_callbacks = []
        if next_event_callback is not None:
            self._next_event_callbacks.append(next_event_callback)

    def initialize(self, backend):
        self.backend = backend

    def add_next_event_callback(self, func: CallbackFunction):
        self._next_event_callbacks.append(func)

    def trigger_next_callback(self, sample_chunk):
        for func in self._next_event_callbacks:
            func(sample_chunk)

    @abc.abstractmethod
    def data_generator(self) -> Iterator[Optional[SampleChunk]]:
        """
        All signal producers need to define a data_generator() method that creates a generator iterator that produces
        the data when called.
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


def chunker(gen, chunk_size=100) -> Iterator[Optional[SampleChunk]]:
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
    chunk_n = 0
    chunk_mixed = False
    # noinspection PyUnusedLocal
    chunk_mixed_start_offset = 0

    while True:

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
            # noinspection PyUnboundLocalVariable
            sample_chunk_obj = copy.copy(sample_chunk_obj)  # type: SampleChunk
            sample_chunk_obj.data = next_chunk.copy()

            chunk_mixed_start_offset = chunk_size - curr_data_sample

            sample_chunk_obj.chunk_n = chunk_n
            sample_chunk_obj.mixed_producer = chunk_mixed
            sample_chunk_obj.mixed_start_offset = 0 if chunk_mixed_start_offset < 0 else chunk_mixed_start_offset

            # print("\n\t", chunk_n, "chunk return", sample_chunk_obj.producer_identifier,
            #       'mixed=', chunk_mixed, "curr_chunk_sample",
            #       curr_chunk_sample, "curr_data_sample", curr_data_sample, "offset", chunk_size - curr_data_sample)

            yield sample_chunk_obj

            chunk_n += 1
            chunk_mixed = False
            curr_chunk_sample = 0
        else:
            # this chunk was not filled by the input stim/chunk, so taken another bite out of the next one
            # by looping again
            chunk_mixed = True


class MixedSignal(SignalProducer):
    """
    The MixedSignal class is a simple class that takes a list of signal producer objects as it's input and combines them
    into one signal producer that generates a channel for each. Basically it combines data stored in different numpy
    arrays into a one array.
    """

    def __init__(self, stims, identifier=None, next_event_callback=None):
        """
        Create the MixedSignal object that will combine these stims into one signal
        """

        dtypes = set(s.dtype for s in stims)
        if len(dtypes) > 1:
            raise ValueError("Cannot created mixed signal from signals with different dtypes: %s" % (
                ', '.join('%s:%s' % (s.identifier, s.dtype) for s in stims)))
        _dtype = dtypes.pop()
        assert _dtype == SignalProducer.SUPPORTED_DTYPES[0]

        self._stims = stims

        super(MixedSignal, self).__init__(type_='_mixed',
                                          instance_identifier=identifier or '|'.join(s.identifier for s in stims),
                                          next_event_callback=next_event_callback)

        # Grab a chunk from each generator to see how big their chunks are, we will need to make sure they are all the
        # same size later when we output a single chunk with multiple channels.
        data_gens = [s.data_generator() for s in self._stims]
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

    def data_generator(self) -> Iterator[Optional[SampleChunk]]:
        """
        Create a data generator for this signal. Each signal passed to the constructor will be yielded as a separate
        column of the data chunk returned by this generator.
        """

        # Initialize data generators for these signals in the play list.
        # Wrap each generator in a chunker with the same size.
        data_gens = [chunker(s.data_generator(), self.chunk_size) for s in self._stims]

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

            chunk = SampleChunk(data=self._data, producer_identifier=self.identifier,
                                producer_instance_n=self.producer_instance_n)
            self.trigger_next_callback(chunk)
            yield chunk
