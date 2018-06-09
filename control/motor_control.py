import numpy as np

from audio.signal_producer import SignalProducer, SampleChunk


class BallControl(SignalProducer):

    def __init__(self, num_samples_period=400, next_event_callbacks=None):

        # Attach event next callbacks to this object, since it is a signal producer
        super(BallControl, self).__init__(next_event_callbacks=next_event_callbacks, dtype=np.uint8)

        self.num_samples_period = num_samples_period

        # The ball signal. Two digital signals,
        self._data = np.zeros((num_samples_period, 2), dtype=np.uint8)

        half_period = round(num_samples_period/2)
        quarter_period = round(num_samples_period/4)

        self._data[0:half_period, 0] = 1
        self._data[:, 1] = np.roll(self._data[:, 0], quarter_period)

    def data_generator(self):
        while True:
            yield SampleChunk(data=self._data, producer_id=self.producer_id)



