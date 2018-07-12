import numpy as np

from audio.signal_producer import SignalProducer, SampleChunk


class BallControlSignal(SignalProducer):
    """
    BallControlSignal generates a 2-channel digital signal to control the speed of rotation of servo motor connected
    to the fly tracking ball. This allows us to generate fake movements in the ball for testing responses of the system
    in a simulation of closed loop experiments.
    """

    def __init__(self, periods, durations, loop=True, sample_rate = 10000.0, next_event_callbacks=None):
        """
        Create the BallControlSignal based on parameters.

        :param periods: An array or list of period lengths (in milliseconds) for the ball signal, this determines speed.
        :param durations: An array or list of durations (in seconds) for each of the periods specified.
        :param loop: Loop the signal indefinitely or not?
        :param sample_rate: The sample rate of the signal.
        :param next_event_callbacks: A list of callables that will be triggered when the generator for this signal is
        is nexted.
        """

        # Attach event next callbacks to this object, since it is a signal producer
        super(BallControlSignal, self).__init__(next_event_callbacks=next_event_callbacks, dtype=np.uint8)

        periods = np.asarray(periods)
        durations = np.asarray(durations)

        # The total number of samples should be the sum of each periods duration times the sample rate.
        self.total_samples = int(sum(np.round(durations * sample_rate)))

        # Allocate the sample data, two channels needed to signal the motor
        self._data = np.zeros((self.total_samples, 2), dtype=np.uint8)

        sample_idx = 0
        i = 0
        for period in periods:

            # Create the signal for this part of the total signal. Generate the waveform with this period for the
            # correct duration.
            num_samples_period = int(period * (sample_rate / 1000))
            num_samples_in_duration = int(np.round(durations[i] * sample_rate))

            # Get the number of samples for fractions of the period
            half_period = round(num_samples_period / 2)
            quarter_period = round(num_samples_period / 4)

            # Make one period of the signal
            s = np.zeros((num_samples_period, 2), dtype=np.uint8)
            s[0:half_period, 0] = 1
            s[:, 1] = np.roll(s[:, 0], quarter_period)

            # We are going to generate indices into the above signal of appropriate length
            sig_idx = np.mod(np.asarray([j for j in range(num_samples_in_duration)]), num_samples_period)

            self._data[sample_idx:(sample_idx+num_samples_in_duration),:] = s[sig_idx,:]
            sample_idx = sample_idx + num_samples_in_duration
            i = i + 1

        self._zero_signal = np.zeros(shape=self._data.shape, dtype=np.uint8)

        # Should the signal be periodic or not.
        self.loop = loop

    def data_generator(self):

        isDone = False

        while True:
            if not isDone:
                yield SampleChunk(data=self._data, producer_id=self.producer_id)

                # If we are not looping, we are done with the signal.
                if not self.loop:
                    isDone = True

            else:
                # We are done, just yield zeros.
                yield SampleChunk(data=self._zero_signal, producer_id=self.producer_id)


