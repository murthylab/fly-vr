import numpy as np

import PyDAQmx as daq
from PyDAQmx.DAQmxCallBack import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxFunctions import *

from flyvr.audio.signal_producer import SignalProducer, SampleChunk


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
        """

        # Attach event next callbacks to this object, since it is a signal producer
        super(TwoPhotonController, self).__init__(dtype=np.uint8)

        self.start_channel_name = start_channel_name
        self.stop_channel_name = stop_channel_name
        self.next_file_channel_name = next_file_channel_name
        self.channel_names = [start_channel_name, stop_channel_name, next_file_channel_name]

        # Setup data for the default signals
        self.start_signal = np.zeros((self.SIGNAL_LENGTH, 3), dtype=np.uint8)
        self.start_signal[0:self.SIGNAL_LENGTH, 0] = 1
        self.next_signal = np.zeros((self.SIGNAL_LENGTH * 2, 3), dtype=np.uint8)
        self.next_signal[0:self.SIGNAL_LENGTH, 0] = 1
        self.next_signal[self.SIGNAL_LENGTH:self.SIGNAL_LENGTH * 2, 2] = 1

        self._playlist = self._signals = self._shuffle_playback = self._playback_order = None
        self.set_playlist(audio_stim_playlist)

    def set_playlist(self, audio_stim_playlist):
        self._playlist = audio_stim_playlist

        # Ok, we need to create a generator that is sychronized with the provided audio stimulus playlist. First step,
        # we want to produce exactly the same size underlying sample data. Look at each stimulus a create a zero matrix
        # for it.
        self._signals = [np.zeros((stim.num_samples, 3), dtype=np.uint8) for stim in audio_stim_playlist]

        # Now, we want to put a next file signal at the start of every stimulus signal
        for signal in self._signals:
            # noinspection PyPep8Naming
            N = min([self.next_signal.shape[0], signal.shape[0]])
            signal[0:N, :] = self.next_signal[0:N, :]

        # Copy the state of the audio stimulus play back.
        self._shuffle_playback = audio_stim_playlist.shuffle_playback
        self._playback_order = np.arange(len(self._signals))

    def data_generator(self):

        stim_idx = 0

        # Is this the first time this generator has been called
        never_sent_start = True

        # If we are shuffling, copy the seed first, then create a new RNG with the same seed, then generate the same
        # random permutation.
        if self._shuffle_playback:
            random_seed = self._playlist.random_seed
            rng = np.random.RandomState()
            rng.seed(random_seed)
            playback_order = rng.permutation(len(self._signals))
        else:
            rng = None
            playback_order = np.arange(len(self._signals))

        # Now, go through the list one at a time, call next on each one of their generators
        while True:

            play_idx = playback_order[stim_idx]

            data = self._signals[play_idx]

            if never_sent_start:
                never_sent_start = False
                start_signal = np.copy(data)
                start_signal[0:self.SIGNAL_LENGTH, 0] = 1
                start_signal[:, 2] = 0
                yield SampleChunk(producer_id=self.producer_id, data=start_signal)
            else:
                yield SampleChunk(producer_id=self.producer_id, data=data)

            stim_idx = stim_idx + 1

            # If we are at the end, then either go back to beginning or reshuffle
            if stim_idx == len(self._signals):
                stim_idx = 0

                if self._shuffle_playback:
                    playback_order = rng.permutation(len(self._signals))

    # noinspection PyUnresolvedReferences,PyPep8Naming
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
