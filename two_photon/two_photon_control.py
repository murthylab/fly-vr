import numpy as np

import PyDAQmx as daq
from PyDAQmx.DAQmxCallBack import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxFunctions import *


from audio.signal_producer import SignalProducer, SampleChunk


class TwoPhotonController(SignalProducer):
    """
    A simple class to handle sending messages to the two photon imaging system via NI DAQ digital output channels. In
    essence, this is a signal producer class that outputs digital samples for three channels specifying the start, next,
    and stop signals for the DAQ. The key thing is that its output is tied to another SignalProducer, the
    AudioStimPlaylist.
    """

    SIGNAL_LENGTH = 5

    def __init__(self, start_channel_name, next_file_channel_name, stop_channel_name, audio_stim_playlist):
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

        # Setup data for the default signals
        self.start_signal = np.zeros((self.SIGNAL_LENGTH, 3), dtype=np.uint8)
        self.start_signal[0:self.SIGNAL_LENGTH, 0] = 1
        self.next_signal = np.zeros((self.SIGNAL_LENGTH*2, 3), dtype=np.uint8)
        self.next_signal[0:self.SIGNAL_LENGTH, 0] = 1
        self.next_signal[self.SIGNAL_LENGTH:self.SIGNAL_LENGTH*2, 2] = 1

        self.set_playlist(audio_stim_playlist)

    def set_playlist(self, audio_stim_playlist):

        # Ok, we need to create a generator that is sychronized with the provided audio stimulus playlist. First step,
        # we want to produce exactly the same size underlying sample data. Look at each stimulus a create a zero matrix
        # for it.
        self.signals = [np.zeros((stim.data.shape[0], 3), dtype=np.uint8) for stim in audio_stim_playlist.stims]

        # Now, we want to put a next file signal at the start of every stimulus signal
        for signal in self.signals:
            N = min([self.next_signal.shape[0], signal.shape[0]])
            signal[0:N, :] = self.next_signal[0:N, :]


        # Copy the state of the audio stimulus play back.
        self.shuffle_playback = audio_stim_playlist.shuffle_playback
        self.playback_order = np.arange(len(self.signals))

        # If we are shuffling, copy the seed first, then create a new RNG with the same seed, then generate the same
        # random permutation.
        if self.shuffle_playback:
            self.random_seed = audio_stim_playlist.random_seed
            self.rng = np.random.RandomState()
            self.rng.seed(self.random_seed)
            self.playback_order = self.rng.permutation(len(self.signals))

        self.never_sent_start = True

    def data_generator(self):

        stim_idx = 0

        # Now, go through the list one at a time, call next on each one of their generators
        while True:

            play_idx = self.playback_order[stim_idx]

            data = self.signals[play_idx]

            if self.never_sent_start:
                self.never_sent_start = False
                N = min([self.SIGNAL_LENGTH, data.shape[0]])
                start_signal = np.copy(data)
                start_signal[0:self.SIGNAL_LENGTH, 0] = 1
                start_signal[:, 2] = 0
                yield SampleChunk(producer_id=self.producer_id, data=start_signal)
            else:
                yield SampleChunk(producer_id=self.producer_id, data=data)

            stim_idx = stim_idx + 1;

            # If we are at the end, then either go back to beginning or reshuffle
            if (stim_idx == len(self.signals)):
                stim_idx = 0

                if (self.shuffle_playback):
                    self.playback_order = self.rng.permutation(len(self.signals))


    def send_2P_stop_signal(self, dev_name="Dev1"):
        stop_signal = np.zeros((TwoPhotonController.SIGNAL_LENGTH + 20, 3), dtype=np.uint8)
        stop_signal[0:TwoPhotonController.SIGNAL_LENGTH, 1] = 1

        cha_name = [dev_name + '/' + ch for ch in self.channel_names]  # append device name
        cha_string = ", ".join(cha_name)

        task = daq.Task()
        task.CreateDOChan(cha_string, "", DAQmx_Val_ChanForAllLines)
        task.StartTask()
        task.WriteDigitalLines(stop_signal.shape[0], False, DAQmx_Val_WaitInfinitely,
                               DAQmx_Val_GroupByScanNumber, stop_signal, None, None)
        task.StopTask()

def main():
    pass


if __name__ == "__main__":
    main()
