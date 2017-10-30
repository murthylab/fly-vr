import numpy as np
import abc
import copy

class SignalNextEventData(object):
    """
    A class that encapsulates all the data that SignalProducer's need to send to their callback
    functions when a next generator event occurs.
    """
    def __init__(self, producer_id, channel, metadata, start_sample_num):
        self.producer_id = producer_id
        self.metadata = metadata
        self.start_sample_num = start_sample_num
        self.channel = 0 # FIXME: We need to add support for arbiratry channels

class SampleChunk(object):
    """
    A class that encapsulated numpy arrays containing sample data along with metadata information. This allows us to
    record attributes like where the data was produced.
    """
    def __init__(self, data, producer_id):
        self.data = data
        self.producer_id = producer_id

class SignalProducer(object):
    """
    A general class that abstracts away the key features of signal producers. Its main purpose is to provide a generator
    method interface and to keep track of the history of this generator's execution. AudioStimuli, AudioStimuluPlaylist,
    and others inherit from this class to standardize their interface.
    """
    __metaclass__ = abc.ABCMeta

    # We want to keep track of every instance of a signal producer class. These instance IDs will be appended to their
    # event messages.
    instances_created = 0

    def __init__(self, next_event_callbacks=None):

        # Use the number of instances created to set an ID for this instance
        self.producer_id = SignalProducer.instances_created

        # Increment the class shared number of instances created
        SignalProducer.instances_created += 1

        # If the user passed in a single callback function, we need to put it in a list.
        if next_event_callbacks is not None and not isinstance(next_event_callbacks, list):
            self._next_event_callbacks = [next_event_callbacks]
        else:
            self._next_event_callbacks = next_event_callbacks

    @property
    def next_event_callbacks(self):
        """
        Get the callback or list of callback functions to execute when this producer generates data.

        :return: The list of callback functions.
        """
        return self._next_event_callbacks

    @next_event_callbacks.setter
    def next_event_callbacks(self, next_event_callbacks):
        """
        Set the callback or list of callback functions to execute when this producer generates data.

        :param next_event_callbacks: The callback or list of callbacks
        """

        # If the user provided an attenuator, attenuate the signal
        if next_event_callbacks is not None and not isinstance(next_event_callbacks, list):
            self._next_event_callbacks = [next_event_callbacks]

    def trigger_next_callback(self, message_data, channel=0):
        """
        Trigger any callbacks that have been assigned to this SignalProducer. This methods should be called before
        any yield of a generator created by the signal producer. This allows them to signal next events to other parts
        of the application.

        :param message_data: A dict that contains meta-data associated with this event. Should be relatively small since
        it will be pickled and sent to logging process.
        """

        # Attach the event specific data to this event data. This is the producer and the start sample number
        message = SignalNextEventData(producer_id=self.producer_id, channel=channel, metadata=message_data,
                                            start_sample_num=self.num_samples_generated)
        message.producer_id = self.producer_id
        message.start_sample_num = self.num_samples_generated

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
            sample_chunk_obj = gen.next()
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
