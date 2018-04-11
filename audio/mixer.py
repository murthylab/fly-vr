import numpy as np
from multiprocessing import Lock

from common.tools import chunker

class Mixer(object):
    """
    This class handles combining multiple channels of DAQ output signals into one analog data buffer. It acts as an
    interface for applications to the DAQ IOTask class. It captures coarse grained history of stimuli\signal generation
    history.
    """
    def __init__(self, channel_labels, daq_channel_names, data_producers):
        self.daq_channel_names = daq_channel_names
        self._producers = dict(list(zip(channel_labels, data_producers)))
        self._lock = Lock()

    def set_channel_producer(self, channel_label, producer):
        """
        Set the producer for a particular channel. This method is thread safe.

        :param channel_label: The label of the channel to set the producer of.
        :param producer: The producer to use for assignment.
        :return:
        """
        self._lock.acquire()
        self._producers[channel_label] = producer
        self._lock.release()

    def data_generator(self, chunk_size=100):

        # Create chunked generators for each producer
        self._chunked_pro_gens = [chunker(pro.data_generator(), chunk_size) for label,pro in self._producers.items()]

        while True:
            channel_chunks = [next(chan_chunker) for chan_chunker in self._chunked_pro_gens]
            mixed_chunk = np.concatenate(channel_chunks, axis=1)
            yield mixed_chunk


