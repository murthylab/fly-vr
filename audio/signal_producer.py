import numpy as np
import abc
import copy

class SignalNextEventData(object):
    """
    A class that encapsulates all the data that SignalProducer's need to send to their control
    functions when a next generator event occurs.
    """
    def __init__(self, producer_id, channel, metadata, num_samples):
        self.producer_id = producer_id
        self.metadata = metadata
        self.num_samples = num_samples
        self.channel = channel

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

    def __init__(self, next_event_callbacks=None, dtype=np.float64):
        """
        Create a signal producer instance.

        :param next_event_callbacks:
        :param dtype: The underlying data type for the numpy array that this class produces. float64 by default.
        """

        # Use the number of instances created to set an ID for this instance
        self.producer_id = SignalProducer.instances_created

        # Increment the class shared number of instances created
        SignalProducer.instances_created += 1

        # Store dtype for this producer
        self.dtype = dtype

        # If the user passed in a single callback function, we need to put it in a list.
        if next_event_callbacks is not None and not isinstance(next_event_callbacks, list):
            self._next_event_callbacks = [next_event_callbacks]
        else:
            self._next_event_callbacks = next_event_callbacks

        # Create a basic event message with the name of the class
        self.event_message = {"name": type(self).__name__}

    @property
    def next_event_callbacks(self):
        """
        Get the control or list of control functions to execute when this producer generates data.

        :return: The list of control functions.
        """
        return self._next_event_callbacks

    @next_event_callbacks.setter
    def next_event_callbacks(self, next_event_callbacks):
        """
        Set the control or list of control functions to execute when this producer generates data.

        :param next_event_callbacks: The control or list of callbacks
        """

        # If the user provided an attenuator, attenuate the signal
        if next_event_callbacks is not None and not isinstance(next_event_callbacks, list):
            self._next_event_callbacks = [next_event_callbacks]

    def trigger_next_callback(self, message_data, num_samples, channel=0):
        """
        Trigger any callbacks that have been assigned to this SignalProducer. This methods should be called before
        any yield of a generator created by the signal producer. This allows them to signal next events to other parts
        of the application.

        :param message_data: A dict that contains meta-data associated with this event. Should be relatively small since
        it will be pickled and sent to logging process.
        """

        # Attach the event specific data to this event data. This is the producer and the start sample number
        message = SignalNextEventData(producer_id=self.producer_id, num_samples=num_samples, channel=channel,
                                      metadata=message_data)
        message.producer_id = self.producer_id

        if self.next_event_callbacks is not None:
            for func in self.next_event_callbacks:
                func(message)

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
    while True:

        if curr_data_sample == num_samples:
            sample_chunk_obj = next(gen)
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
        sz = min(chunk_size-curr_chunk_sample, num_samples-curr_data_sample)
        if data.ndim == 1:
            next_chunk[curr_chunk_sample:(curr_chunk_sample + sz)] = data[curr_data_sample:(curr_data_sample + sz)]
        else:
            next_chunk[curr_chunk_sample:(curr_chunk_sample+sz), :] = data[curr_data_sample:(curr_data_sample + sz), :]

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

    def __init__(self, signals, next_event_callbacks=None):
        """
        Create the MixedSignal object that will combine these signals into one signal.

        :param signals: The list of signals to combine, one for each channel.
        :param next_event_callbacks: A list of callables to trigger when a next is called on this signal producer.
        """

        self.signals = signals

        # Check the dtypes of each producer to make sure they are compatible
        dtypes = [sig.dtype for sig in self.signals]

        dtype = dtypes[0]

        # Make sure all signals have the same dtype.
        if not all(typ == dtype for typ in dtypes):
            raise ValueError("Cannot created mixed signal from signals with different dtypes.")

        # Attach event next callbacks to this object, since it is a signal producer
        super(MixedSignal, self).__init__(next_event_callbacks=next_event_callbacks, dtype=dtype)

        # Setup a dictionary for the parameters of the stimulus. We will send this as part
        # of an event message to the next_event_callbacks
        self.event_message['channels'] = [sig.event_message for sig in self.signals]

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

        self.chunk_size = min(chunk_sizes)
        self.chunk_width = sum(self.chunk_widths)

        self._data = np.zeros((self.chunk_size, self.chunk_width), dtype=self.dtype)

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
                    self._data[:, channel_idx:channel_idx+self.chunk_widths[i]] = chunks[i].data

                channel_idx = channel_idx + self.chunk_widths[i]


            # We are about to yield, send an event to our callbacks
            #self.trigger_next_callback(message_data=self.event_message, num_samples=mix_chunk.shape[0], channel=mix_chunk.shape[1])

            yield SampleChunk(data=self._data, producer_id=self.producer_id)


class ConstantSignal(SignalProducer):
    """
    A very simple signal that generates a constant value.
    """

    def __init__(self, constant, next_event_callbacks=None):

        # Attach event next callbacks to this object, since it is a signal producer
        super(ConstantSignal, self).__init__(next_event_callbacks=next_event_callbacks)

        self.constant = constant

        self.chunk = SampleChunk(data=np.array([self.constant], dtype=self.dtype), producer_id=self.producer_id)

        self.event_message['constant'] = constant

    def data_generator(self):
        while True:

            # We are about to yield, send an event to our callbacks
            self.trigger_next_callback(message_data=self.event_message, num_samples=self.chunk.data.shape[0])

            yield self.chunk

