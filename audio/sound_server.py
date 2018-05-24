import sounddevice as sd

import time
import sys
import threading
import multiprocessing
from multiprocessing import Event

import numpy as np

from audio.stimuli import SinStim, AudioStim
from audio.io_task import chunker

import types

from common.concurrent_task import ConcurrentTask
from common.logger import DatasetLogServer

class SoundServer:
    """
    The SoundServer class is a light weight interface  built on top of sounddevice for setting up and playing auditory
    stimulii via a sound card. It handles the configuration of the sound card with low latency ASIO drivers (required to
    be present on the system) and low latency settings. It also tracks information about the number and timing of
    samples be outputed within its device control so synchronization with other data sources in the experiment can be
    made.
    """

    def __init__(self, flyvr_shared_state=None):
        """
        Setup the initial state of the sound server. This does not open any devices for play back. The start_stream
        method must be invoked before playback can begin.
        """

        # We will update variables related to audio playback in flyvr's shared state data if provided
        self.flyvr_shared_state = flyvr_shared_state

        # No data generator has been set yet
        self._data_generator = None

        # Once, we no the block size and number of channels, we will pre-allocate a block of silence data
        self._silence = None

        # Setup a stream end event, this is how the control will signal to the main thread when it exits.
        self.stream_end_event = multiprocessing.Event()

        # The process we will spawn the sound server thread in.
        self.task = ConcurrentTask(task = self._sound_server_main, comms='pipe')

    # This is how many records of calls to the callback function we store in memory.
    CALLBACK_TIMING_LOG_SIZE = 10000

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
        if self._stream is not None:
            if data_generator is None:
                self._data_generator = None
            else:
                self._data_generator = chunker(data_generator, chunk_size=self._stream.blocksize)

    def _play(self, stim):
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

    def start_stream(self, data_generator=None, num_channels=1, dtype='float32',
                    sample_rate=44100, frames_per_buffer=0, suggested_output_latency=0.005):
        """
        Start a stream of audio data for playback to the device

        :param num_channels: The number of channels for playback, should be 1 or 2. Default is 1.
        :param dtype: The datatype of each samples. Default is 'float32' and the only type currently supported.
        :param sample_rate: The sample rate of the signal in Hz. Default is 44100 Hz
        :param frames_per_buffer: The number of frames to output per write to the sound card. This will effect latency.
        try to keep it as a power of 2 or better yet leave it to 0 and allow the sound card to pick it based on your
        suggested latency. Default is 0.
        :param suggested_output_latency: The suggested latency in seconds for output playback. Set as low as possible
        without glitches in audio. Default is 0.005 seconds.
        :return: None
        """

        # Keep a copy of the parameters for the stream
        self._num_channels = num_channels
        self._dtype = dtype
        self._sample_rate = sample_rate
        self._frames_per_buffer = frames_per_buffer
        self._suggested_output_latency = suggested_output_latency
        self._start_data_generator = data_generator

        # Start the task
        self.task.start()

        return SoundStreamProxy(self)

    def _sound_server_main(self, msg_receiver):
        """
        The main process function for the sound server. Handles actually setting up the sounddevice object\stream.
        Waits to receive objects to play on the stream, sent from other processes using a Queue or Pipe.

        :return: None
        """

        # Initialize number of samples played to 0
        self.samples_played = 0

        # Set the default device to the ASIO driver
        sd.default.device = 'ASIO4ALL'

        # Lets keep track of some timing statistics during playback

        self.callback_timing_log = np.zeros((self.CALLBACK_TIMING_LOG_SIZE, 5))
        self.callback_timing_log_index = 0

        # Setup a dataset to store timing information logged from the callback
        self.timing_log_num_fields = 3
        self.flyvr_shared_state.logger.create("/fictrac/soundcard_synchronization_info",
                                              shape = [2048, self.timing_log_num_fields],
                                              maxshape = [None, self.timing_log_num_fields], dtype = np.float64,
                                              chunks = (2048, self.timing_log_num_fields))

        # open stream using control
        self._stream = sd.OutputStream(samplerate=self._sample_rate, blocksize=self._frames_per_buffer,
                                         latency=self._suggested_output_latency, channels=self._num_channels,
                                         dtype=self._dtype,callback=self._make_callback(),
                                         finished_callback=self._stream_end)

        # Print the aquired output latency estimate
        print("Output Latency: ", self._stream.latency)

        # # Setup data generator, the control has been setup to reference this classes data_generator field
        # if self._start_data_generator is None:
        #     self.data_generator = None
        # elif isinstance(self._start_data_generator, AudioStim):
        #     data_generator = self.play(data_generator)
        # elif isinstance(self._start_data_generator, types.GeneratorType):
        #     # Setup the data generator, make sure it outputs chunks of the appropriate block size for the device.
        #     self.data_generator = chunker(self._start_data_generator, chunk_size=self._stream.blocksize)
        #

        # Initialize a block of silence to be played when the generator is none.
        self._silence = np.squeeze(np.zeros((self._stream.blocksize, self._stream.channels), dtype=self._stream.dtype))

        # Setup up for playback of silence.
        self.data_generator = None

        # Loop until the stream end event is set.
        with self._stream:
            while not self.stream_end_event.is_set() and \
                    self.flyvr_shared_state.is_running_well():

                # Wait for a message to come
                msg = msg_receiver.recv()
                if isinstance(msg, AudioStim) or msg is None:
                    self._play(msg)

    def _stream_end(self):
        """
        Invoked at the end of stream playback by sounddevice. We can do any cleanup we need here.
        """

        # Trigger the event that marks a stream end, the main loop thread is waiting on this.
        self.stream_end_event.set()

    def _make_callback(self):
        """
        Make control for the stream playback. Reference self.data_generator to get samples.

        :return: A control function to provide sounddevice.
        """

        # Create a control function that uses the provided data generator to get sample blocks
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

            # self.callback_timing_log[self.callback_timing_log_index, 0] = self.samples_played
            # self.callback_timing_log[self.callback_timing_log_index, 1] = time_info.currentTime
            # self.callback_timing_log[self.callback_timing_log_index, 2] = time.clock() * 1000
            # self.callback_timing_log[self.callback_timing_log_index, 3] = time_info.outputBufferDacTime

            # Update the number of samples played in the shared state counter
            if self.flyvr_shared_state is not None:
                self.flyvr_shared_state.logger.log("/fictrac/soundcard_synchronization_info",
                                np.array([0,#self.flyvr_shared_state.FICTRAC_FRAME_NUM.value,
                                          self.samples_played,
                                          time.clock() * 1000]))

                #self.flyvr_shared_state.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN.value += frames

            # self.callback_timing_log_index = self.callback_timing_log_index + 1
            # if self.callback_timing_log_index >= self.callback_timing_log.shape[0]:
            #     self.callback_timing_log_index = 0

            if len(data) < len(outdata):
                outdata.fill(0)
                raise sd.CallbackStop
            else:
                outdata[:,0] = data

        return callback

class SoundStreamProxy:
    """
    The SoundStreamProxy class acts as an interface to a SoundServer object that is running on another process. It
    handles sending commands to the object on the other process.
    """

    def __init__(self, sound_server):
        """
        Initialize the SoundStreamProxy with an already setup SoundServer object. This assummes that the server is
        running and ready to receive commands.

        :param sound_server: The SoundServer object to issue commands to.
        """
        self.sound_server = sound_server
        self.task = self.sound_server.task

    def play(self, stim):
        """
        Send audio stimulus to the sound server for immediate playback.

        :param stim: The AudioStim object to play.
        :return: None
        """
        self.task.send(stim)

    def silence(self):
        """
        Set current playback to silence immediately.

        :return: None
        """
        self.play(None)

    def close(self):
        """
        Signal to the server to shutdown the stream.

        :return: None
        """
        self.sound_server.stream_end_event.set()

        # We send the server a junk signal. This will cause the message loop to wake up, skip the message because its
        # junk, and check whether to exit, which it will see is set and will close the stream. Little bit of a hack but
        # it gets the job done I guess.
        self.play("KILL")

        # Wait till the server goes away.
        while self.task.process.is_alive():
            time.sleep(0.1)


def main():
    from flyvr import SharedState

    global TIMING_IDX
    TIMING_IDX = 0

    CHUNK_SIZE = 128
    stim1 = SinStim(frequency=200, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)
    stim2 = SinStim(frequency=300, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)
    stims = [stim1, None]

    # Setup logging server
    log_server = DatasetLogServer()
    logger = log_server.start_logging_server("test.h5")

    shared_state = SharedState(None, logger)

    sound_server = SoundServer(flyvr_shared_state=shared_state)
    sound_client = sound_server.start_stream(frames_per_buffer=CHUNK_SIZE, suggested_output_latency=0.002)

    from common.mmtimer import MMTimer
    def tick():
        global TIMING_IDX
        sound_client.play(stims[TIMING_IDX % 2])
        TIMING_IDX = TIMING_IDX + 1

    t1 = MMTimer(1000, tick)
    t1.start(True)

    while time.clock() < 10:
        pass

    # Close the stream down.
    sound_client.close()
    log_server.stop_logging_server()
    log_server.wait_till_close()

if __name__ == "__main__":
    main()