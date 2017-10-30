import numpy as np

from audio.signal_producer import SignalProducer, SampleChunk


class TwoPhotonController(SignalProducer):
    """
    A simple class to handle sending messages to the two photon imaging system via NI DAQ digital output channels. In
    essence, this is a signal producer class that outputs digital samples for three channels specifying the start, next,
    and stop signals for the DAQ. The key thing is that its output is tied to another SignalProducer, the
    AudioStimPlaylist.
    """

    def __init__(self, start_channel_name, next_file_channel_name, stop_channel_name, num_samples=50):
        """
        Initialize the controller with the names of the control channels on the NI DAQ device. Each one should be a
        digital channel that is connected to the 2P imaging system.

        :param start_channel_name: The name of the digital channel to send the start signal on
        :param next_file_channel_name: The name of the digtial channel to sent the next file signal on.
        :param stop_channel_name: The name of the digital channel to send the stop signal on
        :param producer: The signal producer that is driving this two photon controller.
        """

        # Attach event next callbacks to this object, since it is a signal producer
        super(TwoPhotonController, self).__init__()

        self.start_channel_name = start_channel_name
        self.stop_channel_name = stop_channel_name
        self.next_file_channel_name = next_file_channel_name
        self.channel_names = [start_channel_name, stop_channel_name, next_file_channel_name]
        self.num_samples = num_samples

        # These three public boolean values dictate the state of the generator. If set to true they will trigger a
        # signal to be sent on the next sample generation. They will then be set back to False.
        self.send_start_trigger = True;
        self.send_next_trigger = False;
        self.send_stop_trigger = False;

        self.start_signal = SampleChunk(producer_id=self.producer_id, data=np.zeros((num_samples, 3), dtype=np.uint8))
        self.start_signal.data[0:4,0] = 1
        self.next_signal = SampleChunk(producer_id=self.producer_id, data=np.zeros((num_samples, 3), dtype=np.uint8))
        self.next_signal.data[0:4,0] = 1
        self.next_signal.data[0:4,2] = 1
        self.stop_signal = SampleChunk(producer_id=self.producer_id, data=np.zeros((num_samples, 3), dtype=np.uint8))
        self.stop_signal.data[:, 1] = 1
        self.zero_signal = SampleChunk(producer_id=self.producer_id, data=np.zeros((num_samples, 3), dtype=np.uint8))

        self.never_sent_start = True

    def make_next_signal_callback(self):
        def callback(event_message):
            self.send_next_trigger = True
        return callback

    def make_stop_signal_callback(self):
        def callback(event_message):
            self.send_stop_trigger = True
        return callback

    def make_start_signal_callback(self):
        def callback(event_message):
            self.send_start_trigger = True
        return callback

    def turn_off_triggers(self):
        self.send_start_trigger = False
        self.send_next_trigger = False

    def data_generator(self):
        while True:
            if self.send_start_trigger:
                self.turn_off_triggers()
                self.never_sent_start = False
                yield self.start_signal
            elif self.send_next_trigger:
                self.turn_off_triggers()
                yield self.next_signal
            elif self.send_stop_trigger:
                self.turn_off_triggers()
                yield self.stop_signal
            else:
                yield self.zero_signal