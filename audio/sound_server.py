import sounddevice as sd

import time
import sys
import threading

import numpy as np

from audio.stimuli import SinStim, AudioStim
from audio.io_task import chunker

import types

class SoundServer:
    """
    The SoundServer class is a light weight interface  built on top of sounddevice for setting up and playing auditory
    stimulii via a sound card. It handles the configuration of the sound card with low latency ASIO drivers (required to
    be present on the system) and low latency settings. It also tracks information about the number and timing of
    samples be outputed within its device callback so synchronization with other data sources in the experiment can be
    made.
    """

    def __init__(self, flyvr_shared_state=None):
        """
        Setup the initial state of the sound server. This does not open any devices for play back. The start_stream
        method must be invoked before playback can begin.
        """

        # Set the default device to the ASIO driver
        sd.default.device = 'ASIO4ALL'

        # We will update variables related to audio playback in flyvr's shared state data if provided
        self.flyvr_shared_state = flyvr_shared_state

        # Initialize number of samples played to 0
        self.samples_played = 0

        # Setup a stream end event, this is how the callback will signal to the main thread when it exits.
        self._stream_end_event = threading.Event()

        # Initialize the underlying stream to None, since it still needs to be setup with open_stream
        self.stream = None

        # Lets keep track of some timing statistics during playback
        self.CALLBACK_TIMING_LOG_SIZE = 10000
        self.callback_timing_log = np.zeros((self.CALLBACK_TIMING_LOG_SIZE,5))
        self.callback_timing_log_index = 0

        # No data generator has been set yet
        self._data_generator = None

        # Once, we no the block size and number of channels, we will pre-allocate a block of silence data
        self._silence = None

    @property
    def data_generator(self):
        """
        Get the instance of a generator for producing audio samples for playback

        :return: A generator instance that will yield the next chunk of sample data for playback
        :rtype: Generator
        """
        return self._data_generator

    @data_generator.setter
    def data_generator(self, data_generator):
        """
        Set the generator that will yield the next sample of data.

        :param data_generator: A generator instance.
        """

        # If the stream has been setup and
        # If the generator the user is passing is None, then just set it. Otherwise, we need to set it but make sure
        # it is chunked up into the appropriate blocksize.
        if self.stream is not None:
            if data_generator is None:
                self._data_generator = None
            else:
                self._data_generator = chunker(data_generator, chunk_size=self.stream.blocksize)

    def start_stream(self, data_generator=None, num_channels=1, dtype='float32',
                    sample_rate=44100, frames_per_buffer=0, suggested_output_latency=0.005,
                    timeout=None):
        """
        Start a stream of audio data for playback to the device

        :param data_generator: A data generator to use for producing samples. Or and AudioStim object. This is the source
        of starting samples. If None, silence will be generated. Default is None
        :param num_channels: The number of channels for playback, should be 1 or 2. Default is 1.
        :param dtype: The datatype of each samples. Default is 'float32' and the only type currently supported.
        :param sample_rate: The sample rate of the signal in Hz. Default is 44100 Hz
        :param frames_per_buffer: The number of frames to output per write to the sound card. This will effect latency.
        try to keep it as a power of 2 or better yet leave it to 0 and allow the sound card to pick it based on your
        suggested latency. Default is 0.
        :param suggested_output_latency: The suggested latency in seconds for output playback. Set as low as possible
        without glitches in audio. Default is 0.005 seconds.
        :param timeout: A timeout in seconds to close the stream automatically. None means no timeout. Default is None.
        :return: None
        """

        # Initialize number of samples played to 0
        self.samples_played = 0

        # open stream using callback
        self.stream = sd.OutputStream(samplerate=sample_rate, blocksize=frames_per_buffer,
                                         latency=suggested_output_latency, channels=num_channels,
                                         dtype=dtype,callback=self._make_callback(),
                                         finished_callback=self._stream_end)


        # Setup data generator, the callback has been setup to reference this classes data_generator field
        if data_generator is None:
            self.data_generator = None
        elif isinstance(data_generator, AudioStim):
            data_generator = self.play(data_generator)
        elif isinstance(data_generator, types.GeneratorType):
            # Setup the data generator, make sure it outputs chunks of the appropriate block size for the device.
            self.data_generator = chunker(data_generator, chunk_size=self.stream.blocksize)

        # Preallocate some silence data, this will be used when no data generator is specified.
        self._silence = np.squeeze(np.zeros((self.stream.blocksize, self.stream.channels)))

        # With a stream setup, wait till we get the end stream signal.
        with self.stream:
            if timeout is not None:
                self._stream_end_event.wait(timeout=timeout)
            else:
                self._stream_end_event.wait()

    def play(self, stim):
        """
        Play an audio stimulus through the sound card. This method invokes the data generator of the stimulus to
        generate the data.

        :param stim: An instance of AudioStim or a class that inherits from it.
        :return: None
        """

        # Make sure the user passed and AudioStim instance
        if isinstance(stim, AudioStim):
            self.data_generator = stim.data_generator()
        elif stim is None:
            self.data_generator = None
        else:
            raise ValueError("The play method of SoundServer only takes instances of AudioStim objects or those that" +
                             "inherit from this base classs. ")

    def _stream_end(self):
        """
        Invoked at the end of stream playback by sounddevice. We can do any cleanup we need here.
        """

        # Trigger the event that marks a stream end, the main loop thread is waiting on this.
        self._stream_end_event.set()

    def _make_callback(self):
        """
        Make callback for the stream playback. Reference self.data_generator to get samples.

        :return: A callback function to provide sounddevice.
        """

        # Store the instance of our sample data generator in the instance of this class
        self.data_generator = self.data_generator

        # Create a callback function that uses the provided data generator to get sample blocks
        def callback(outdata, frames, time_info, status):

            if status.output_underflow:
                print('Output underflow: increase blocksize?', file=sys.stderr)
                raise sd.CallbackAbort

            # Make sure all is good
            assert not status

            try:

                # If we have no data generator set, then play silence. If not, call its next method
                if self._data_generator is None:
                    data = self._silence
                else:
                    data_chunk = next(self._data_generator).data
                    data = data_chunk.data

                # Make extra sure the length of the data we are getting is the correct number of samples
                assert(len(data) == frames)

            except StopIteration:
                print('Audio generator produced StopIteration, something went wrong! Aborting playback', file=sys.stderr)
                raise sd.CallbackAbort

            # Lets keep track of some running information
            self.samples_played = self.samples_played + frames
            self.callback_timing_log[self.callback_timing_log_index, 0] = self.samples_played
            self.callback_timing_log[self.callback_timing_log_index, 1] = time_info.currentTime
            self.callback_timing_log[self.callback_timing_log_index, 2] = time_info.inputBufferAdcTime
            self.callback_timing_log[self.callback_timing_log_index, 3] = time_info.outputBufferDacTime
            self.callback_timing_log[self.callback_timing_log_index, 4] = time.clock() * 1000

            self.callback_timing_log_index = self.callback_timing_log_index + 1
            if self.callback_timing_log_index >= self.callback_timing_log.shape[0]:
                self.callback_timing_log_index = 0

            # Update the number of samples played in the shared state counter
            if self.flyvr_shared_state is not None:
                self.flyvr_shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.value += frames

            if len(data) < len(outdata):
                outdata.fill(0)
                raise sd.CallbackStop
            else:
                outdata[:,0] = data

        return callback

def main():
    global TIMING_IDX
    TIMING_IDX = 0

    CHUNK_SIZE = 128
    stim1 = SinStim(frequency=200, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)
    stim2 = SinStim(frequency=300, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)
    stims = [stim1, None]

    sound_server = SoundServer()

    from common.mmtimer import MMTimer
    def tick():
        global TIMING_IDX
        sound_server.play(stims[TIMING_IDX % 2])
        TIMING_IDX = TIMING_IDX + 1
    t1 = MMTimer(1000, tick)
    t1.start(True)

    sound_server.start_stream(data_generator=stim1.data_generator(), frames_per_buffer=CHUNK_SIZE,
                              suggested_output_latency=0.002, timeout=10)

    np.savetxt('callback_timing.txt', sound_server.callback_timing_log[0:sound_server.callback_timing_log_index, :])

if __name__ == "__main__":
    main()