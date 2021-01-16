import os
import sys
import time
import queue
import logging
import threading

from typing import Optional

import numpy as np
import sounddevice as sd

from flyvr.audio.stimuli import AudioStim, MixedSignal, AudioStimPlaylist
from flyvr.audio.signal_producer import SampleChunk, chunker, chunk_producers_differ
from flyvr.common import Randomizer, BACKEND_AUDIO
from flyvr.common.build_arg_parser import setup_logging


_QUIT = object()


# noinspection PyProtectedMember
def _sd_terminate():
    if sd._initialized:
        sd._terminate()
        return True
    else:
        return False


# noinspection PyProtectedMember
def _sd_initialize():
    if not sd._initialized:
        sd._initialize()


# https://github.com/spatialaudio/python-sounddevice/issues/3
def _sd_reset():
    _sd_terminate()
    _sd_initialize()


class SoundServer(threading.Thread):
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
        assert self.flyvr_shared_state is not None

        self._log = logging.getLogger('flyvr.sound_server')

        # No data generator has been set yet
        self._data_generator = None
        self._stim_playlist = None  # type: Optional[AudioStimPlaylist]

        self._silence_chunk = None  # type: Optional[SampleChunk]
        self._last_chunk = None  # type: Optional[SampleChunk]

        self._stream = self._device = self._num_channels = \
            self._dtype = self._sample_rate = self._frames_per_buffer = None

        self._running = False
        self._q = queue.Queue()

        # Lets keep track of some timing statistics during playback
        self.callback_timing_log = np.zeros((self.CALLBACK_TIMING_LOG_SIZE, 5))
        self.callback_timing_log_index = 0

        self.flyvr_shared_state.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN = 0

        super(SoundServer, self).__init__(daemon=True, name='SoundServer')

    # This is how many records of calls to the callback function we store in memory.
    CALLBACK_TIMING_LOG_SIZE = 10000

    DEVICE_DEFAULT = 'ASIO4ALL v2'
    DEVICE_OUTPUT_DTYPE = 'float32'
    DEVICE_OUTPUT_NUM_CHANNELS = 2
    DEVICE_SAMPLE_RATE = 44100

    DEFAULT_CHUNK_SIZE = 128

    @staticmethod
    def get_audio_output_device_supported_sample_rates(device, channels, dtype, verbose=False):
        supported_samplerates = []
        for fs in (32000, 44100, 48000, 96000, 128000):
            try:
                sd.check_output_settings(device=device, samplerate=fs, channels=channels, dtype=dtype)
            except Exception as e:
                if verbose:
                    print(fs, e)
            else:
                supported_samplerates.append(fs)
        return supported_samplerates

    @staticmethod
    def _iter_compatible_output_devices(show_all=False):
        """ returns (device_name, hostapi_name)"""
        devs = sd.query_devices()
        for info in devs:
            if info['max_output_channels']:
                hostapi_info = sd.query_hostapis(info['hostapi'])
                if show_all or ('ASIO' in hostapi_info.get('name', '')):
                    yield info['name'], hostapi_info.get('name', '')

    @staticmethod
    def list_supported_asio_output_devices(num_channels=DEVICE_OUTPUT_NUM_CHANNELS, dtype=DEVICE_OUTPUT_DTYPE,
                                           out=None, show_all=False):
        out = sys.stdout if out is None else out

        out.write("All Devices\n")
        for device_name, hostapi_name in SoundServer._iter_compatible_output_devices(show_all=show_all):
            if show_all or ('ASIO' in hostapi_name):
                srs = SoundServer.get_audio_output_device_supported_sample_rates(device_name,
                                                                                 num_channels, dtype)
                out.write('    Name: %s (Driver: %s) Sample Rates: %r\n' % (device_name,
                                                                            hostapi_name,
                                                                            srs))

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
                self._log.info('playing silence')
                self._data_generator = None
            else:
                self._data_generator = chunker(data_generator, chunk_size=self._stream.blocksize)

    @property
    def queue(self):
        return self._q

    def _play(self, stim):
        """
        Play an audio stimulus through the sound card. This method invokes the data generator of the stimulus to
        generate the data.

        :param stim: An instance of AudioStim or a class that inherits from it.
        :return: None
        """
        # fixme: need to make sure that all these other types emit signal_new_playlist_item

        # Make sure the user passed and AudioStim instance
        if isinstance(stim, AudioStim):
            if stim.sample_rate != self._sample_rate:
                raise ValueError('AudioStim not at server samplerate: %s' % self._sample_rate)
            self._log.info('playing AudioStim object: %r' % stim)
            stim.initialize(BACKEND_AUDIO)
            self.data_generator = stim.data_generator()
        elif isinstance(stim, MixedSignal):
            self._log.info('playing MixedSignal object: %r' % stim)
            stim.initialize(BACKEND_AUDIO)
            self.data_generator = stim.data_generator()
        elif isinstance(stim, AudioStimPlaylist):
            self._log.info('playing AudioStimPlaylist object: %r' % stim)
            stim.initialize(BACKEND_AUDIO)
            self.data_generator = stim.data_generator()
            self._stim_playlist = stim
        elif stim is None:
            self._log.info('playing nothing')
            self.data_generator = None
        elif isinstance(stim, str) and (self._stim_playlist is not None):
            if stim in {'play', 'pause'}:
                self._log.info('changing status to %s' % stim)
                self._stim_playlist.play_pause(pause=stim == 'pause')
            else:
                self._log.info('playing playlist item identifier: %s' % stim)
                self.data_generator = self._stim_playlist.play_item(stim)
        else:
            raise ValueError("you must play an AudioStim (or derived),"
                             "the name of a playlist item, or an action 'play', 'pause'")

    def start_stream(self,
                     device=DEVICE_DEFAULT, num_channels=DEVICE_OUTPUT_NUM_CHANNELS,
                     dtype=DEVICE_OUTPUT_DTYPE, sample_rate=DEVICE_SAMPLE_RATE,
                     frames_per_buffer=0):
        """
        Start a stream of audio data for playback to the device

        :param device: The name of the audio device
        :param num_channels: The number of channels for playback, should be 1 or 2. Default is 1.
        :param dtype: The datatype of each samples. Default is 'float32' and the only type currently supported.
        :param sample_rate: The sample rate of the signal in Hz. Default is 44100 Hz
        :param frames_per_buffer: The number of frames to output per write to the sound card. This will effect latency.
        try to keep it as a power of 2
        :return: None
        """

        self._device = device
        self._num_channels = num_channels
        self._dtype = dtype
        self._sample_rate = sample_rate
        self._frames_per_buffer = frames_per_buffer

        assert self._frames_per_buffer > 0

        self._running = True
        self.start()

    # noinspection PyUnusedLocal
    def quit(self, *args, **kwargs):
        self._running = False
        self._q.put(None)

    def run(self):
        # python sounddevice loads the platform specific libraries at import time, which is a different thread
        # to that which gets the output device and does the output. This results, on windows at least when using
        # the ASIO device, on error messages like
        #
        # "Error opening OutputStream: Unanticipated host error [PaErrorCode -9999]:
        #   'Failed to load ASIO driver' [ASIO error 0]
        #
        # https://stackoverflow.com/q/39858212
        # to solve this we reset and re-initialize the souddevice and underlying library (in this thread).
        # at the moment only do this on the one important and tested platform (Windows), but I would not
        # be surprised if it was required all the time
        if os.name == 'nt':
            self._log.debug('resetting sounddevice library')
            _sd_reset()

        # setup a dataset to store timing information logged from the callback
        self.flyvr_shared_state.logger.create("/audio/chunk_synchronization_info",
                                              shape=[2048, SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS],
                                              maxshape=[None, SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS],
                                              dtype=np.int64,
                                              chunks=(2048, SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS))
        self.flyvr_shared_state.logger.log("/audio/chunk_synchronization_info",
                                           int(self._sample_rate),
                                           attribute_name='sample_rate')
        self.flyvr_shared_state.logger.log("/audio/chunk_synchronization_info",
                                           int(self._frames_per_buffer),
                                           attribute_name='sample_buffer_size')

        for cn, cname in enumerate(SampleChunk.SYNCHRONIZATION_INFO_FIELDS):
            self.flyvr_shared_state.logger.log("/audio/chunk_synchronization_info",
                                               str(cname),
                                               attribute_name='column_%d' % cn)

        # open stream using control
        self._stream = sd.OutputStream(device=self._device,
                                       samplerate=self._sample_rate, blocksize=self._frames_per_buffer,
                                       latency=None, channels=self._num_channels,
                                       dtype=self._dtype, callback=self._make_callback(),
                                       finished_callback=self.quit)

        self._log.info('opened %s @ %fHz' % (self._device, self._sample_rate))

        cbf = self._sample_rate / float(self._stream.blocksize)
        self._log.info('buffer size: %d (buffer callback called every %.3fs, at %.1fHz)' % (self._stream.blocksize,
                                                                                            1. / cbf, cbf))

        # initialize a block of silence to be played when the generator is none.
        self._silence_chunk = SampleChunk.new_silence(
            np.squeeze(np.zeros((self._stream.blocksize, self._stream.channels), dtype=self._stream.dtype)))

        # setup initial playback
        try:
            msg = self._q.get_nowait()
            self._log.debug('initial playback: %r' % (msg, ))
            self._play(msg)
        except queue.Empty:
            self._log.debug('initial playback: %r' % None)
            self.data_generator = None  # play silence

        _ = self.flyvr_shared_state.signal_ready(BACKEND_AUDIO)

        if not self.flyvr_shared_state.wait_for_start():
            self._log.info('did not receive start signal')
            self._running = False

        with self._stream:  # starts the stream

            while self._running:
                try:
                    msg = self._q.get(timeout=0.5)
                    if msg is not None:
                        if msg is _QUIT:
                            self._running = False
                        else:
                            self._play(msg)
                except queue.Empty:
                    pass

                if self.flyvr_shared_state.is_stopped():
                    self._running = False

        self._log.info('stopped')

    def _make_callback(self):
        """
        Make control for the stream playback. Reference self.data_generator to get samples.

        :return: A control function to provide sounddevice.
        """

        # Create a control function that uses the provided data generator to get sample blocks
        def callback(outdata, frames, time_info, status):

            if status.output_underflow:
                self._log.error('output underflow: increase blocksize?')
                raise sd.CallbackAbort

            # Make sure all is good
            assert not status

            # Make sure all is good in the rest of the application
            if not self.flyvr_shared_state.is_running_well():
                raise sd.CallbackStop()

            try:
                # If we have no data generator set, then play silence. If not, call its next method
                if self._data_generator is None:
                    chunk = self._silence_chunk
                else:
                    chunk = next(self._data_generator)  # type: SampleChunk
                    if chunk is None:
                        chunk = self._silence_chunk

                # Make extra sure the length of the data we are getting is the correct number of samples
                data = chunk.data
                assert (len(data) == frames)

            except StopIteration:
                self._log.fatal('audio generator produced StopIteration, something went wrong! Aborting playback',
                                exc_info=True)
                raise sd.CallbackAbort

            # same order as SampleChunk.SYNCHRONIZATION_INFO_FIELDS
            row = [self.flyvr_shared_state.FICTRAC_FRAME_NUM,
                   self.flyvr_shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN,
                   self.flyvr_shared_state.DAQ_INPUT_NUM_SAMPLES_READ,
                   self.flyvr_shared_state.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN,
                   self.flyvr_shared_state.VIDEO_OUTPUT_NUM_FRAMES,
                   chunk.producer_instance_n,
                   chunk.chunk_n,
                   chunk.producer_playlist_n,
                   chunk.mixed_producer,
                   chunk.mixed_start_offset]

            self.flyvr_shared_state.logger.log("/audio/chunk_synchronization_info",
                                               np.array(row, dtype=np.int64))

            # noinspection DuplicatedCode
            if chunk_producers_differ(self._last_chunk, chunk):
                self._log.debug('chunk from new producer: %r' % chunk)
                self.flyvr_shared_state.signal_new_playlist_item(chunk.producer_identifier, BACKEND_AUDIO,
                                                                 chunk_producer_instance_n=chunk.producer_instance_n,
                                                                 chunk_n=chunk.chunk_n,
                                                                 chunk_producer_playlist_n=chunk.producer_playlist_n,
                                                                 chunk_mixed_producer=chunk.mixed_producer,
                                                                 chunk_mixed_start_offset=chunk.mixed_start_offset,
                                                                 # ensure identical values to the h5 row
                                                                 fictrac_frame_num=row[0],
                                                                 daq_output_num_samples_written=row[1],
                                                                 daq_input_num_samples_read=row[2],
                                                                 sound_output_num_samples_written=row[3],
                                                                 video_output_num_frames=row[4],
                                                                 # and a time for replay experiments
                                                                 time_ns=time.time_ns())

            if len(data) < len(outdata):
                outdata.fill(0)
                raise sd.CallbackStop
            else:

                if data.ndim == 1 and self._num_channels == 2:
                    outdata[:, 0] = data
                    outdata[:, 1] = data
                else:
                    outdata[:] = data

            self.flyvr_shared_state.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN += frames
            self._last_chunk = chunk

        return callback


def _ipc_main(q, basedirs):
    from flyvr.audio.stimuli import legacy_factory, stimulus_factory
    from flyvr.common.ipc import PlaylistReciever

    pr = PlaylistReciever()
    log = logging.getLogger('flyvr.sound_server.ipc_main')

    log.debug('starting')

    while True:
        elem = pr.get_next_element()
        if elem:
            if 'audio_legacy' in elem:
                stim, = legacy_factory([elem['audio_legacy']], basedirs=basedirs)
            elif 'audio' in elem:
                stim = stimulus_factory(**elem['audio'], basedirs=basedirs)
            elif 'audio_item' in elem:
                stim = elem['audio_item']['identifier']
            elif 'audio_action' in elem:
                stim = elem['audio_action']
            else:
                stim = None

            if stim is not None:
                q.put(stim)


def run_sound_server(options, quit_evt=None):
    from flyvr.common import SharedState, Randomizer
    from flyvr.common.logger import DatasetLogServerThreaded
    from flyvr.audio.util import get_paylist_object

    setup_logging(options)

    log = logging.getLogger('flyvr.main_sound_server')

    playlist_stim, basedirs = get_paylist_object(options, playlist_type='audio',
                                                 # optional because we are also called
                                                 # from flyvr main launcher
                                                 paused_fallback=getattr(options, 'paused', False),
                                                 # dudi requested to preserve the last default
                                                 default_repeat=Randomizer.REPEAT_FOREVER,
                                                 attenuator=None)  # fixme: attenuator from config
    if playlist_stim is not None:
        log.info('initialized audio playlist: %r' % playlist_stim)

    with DatasetLogServerThreaded() as log_server:
        logger = log_server.start_logging_server(options.record_file.replace('.h5', '.sound_server.h5'))
        state = SharedState(options=options, logger=logger, where=BACKEND_AUDIO)

        sound_server = SoundServer(flyvr_shared_state=state)
        if playlist_stim is not None:
            sound_server.queue.put(playlist_stim)

        ipc = threading.Thread(daemon=True, name='AudioIpcThread',
                               target=_ipc_main, args=(sound_server.queue, basedirs))
        ipc.start()

        # starts the thread
        sound_server.start_stream(frames_per_buffer=SoundServer.DEFAULT_CHUNK_SIZE)

        if quit_evt is not None:
            # the single process launcher
            try:
                quit_evt.wait()
            except KeyboardInterrupt:
                sound_server.queue.put(_QUIT)

        sound_server.join()

    log.info('finished')


def main_sound_server():
    import yaml
    import os.path

    from flyvr.common.build_arg_parser import build_argparser, parse_options
    from flyvr.audio.util import plot_playlist
    from zmq.utils.win32 import allow_interrupt

    parser = build_argparser()
    parser.add_argument('--print-devices', action='store_true', help='print available audio devices')
    parser.add_argument('--convert-playlist', help='convert a stimulus playlist to new format')
    parser.add_argument('--paused', action='store_true', help='start paused')
    parser.add_argument('--plot', action='store_true', help='plot the stimulus playlist')

    options = parse_options(parser.parse_args(), parser)

    if options.plot:
        setup_logging(options)

        if not options.playlist.get('audio'):
            return parser.error('Config file contains no audio playlist')

        plot_playlist(options, 'audio')

        return parser.exit(0)

    if options.convert_playlist:
        src = options.convert_playlist
        if os.path.isfile(src):
            pl = AudioStimPlaylist.from_legacy_filename(src)
            dest = options.convert_playlist + '.yml'
            with open(dest, 'wt') as f:
                yaml.dump({'playlist': {'audio': pl.describe()}}, f)

            return parser.exit(0, message='Wrote %s' % dest)

        else:
            return parser.error('Could not find %s' % src)

    if options.print_devices:
        SoundServer.list_supported_asio_output_devices()
        return parser.exit(0)

    quit_evt = threading.Event()

    # noinspection PyUnusedLocal
    def ctrlc(*args):
        quit_evt.set()

    with allow_interrupt(action=ctrlc):
        run_sound_server(options, quit_evt)
