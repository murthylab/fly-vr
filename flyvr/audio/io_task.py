# -*- coding: utf-8 -*-
import os
import time
import queue
import logging
import threading

from typing import Optional


import PyDAQmx as daq
# noinspection PyUnresolvedReferences
from PyDAQmx.DAQmxFunctions import (DAQmxCreateTask, DAQmxCreateAOVoltageChan,
                                    DAQmxCfgSampClkTiming, DAQmxStartTask,
                                    DAQmxWriteAnalogScalarF64, DAQmxWaitForNextSampleClock, DAQmxStopTask,
                                    DAQmxClearTask)
# noinspection PyUnresolvedReferences
from PyDAQmx.DAQmxConstants import (DAQmx_Val_RSE, DAQmx_Val_Volts, DAQmx_Val_Rising, DAQmx_Val_HWTimedSinglePoint,
                                    DAQmx_Val_Acquired_Into_Buffer, DAQmx_Val_ContSamps,
                                    DAQmx_Val_Transferred_From_Buffer,
                                    DAQmx_Val_DoNotAllowRegen, DAQmx_Val_AllowRegen, DAQmx_Val_GroupByChannel,
                                    DAQmx_Val_Auto, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                    DAQmx_Val_Diff,
                                    DAQmx_Val_ChanPerLine)

import numpy as np
from ctypes import byref, c_ulong

from flyvr.audio.signal_producer import chunker, SampleChunk, chunk_producers_differ, SignalProducer
from flyvr.audio.stimuli import AudioStim, AudioStimPlaylist, stimulus_factory
from flyvr.audio.util import get_paylist_object
from flyvr.common import BACKEND_DAQ
from flyvr.common.concurrent_task import ConcurrentTask
from flyvr.common.plot_task import plot_task_daq
from flyvr.common.build_arg_parser import setup_logging
from flyvr.common.ipc import PlaylistReciever

DAQ_SAMPLE_RATE_DEFAULT = 10000

DAQ_NUM_OUTPUT_SAMPLES = 5000
DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT = 250
DAQ_NUM_INPUT_SAMPLES = 10000
DAQ_NUM_INPUT_SAMPLES_PER_EVENT = 10000


INPUT_SYNCHRONIZATION_INFO_FIELDS = ('fictrac_frame_num',
                                     'daq_output_num_samples_written',
                                     'daq_input_num_samples_read',
                                     'sound_output_num_samples_written',
                                     'video_output_num_frames',
                                     'time_ns')
INPUT_SYNCHRONIZATION_INFO_NUM_FIELDS = len(INPUT_SYNCHRONIZATION_INFO_FIELDS)


# noinspection PyPep8Naming
class IOTask(daq.Task):
    """
    IOTask encapsulates the an input-output task that communicates with the NIDAQ. It works with a list of input or
    output channel names.
    """

    def __init__(self, dev_name="Dev1", cha_ids=("ai0",), cha_type="input", cha_names=(),
                 limits=10.0, rate=DAQ_SAMPLE_RATE_DEFAULT,
                 num_samples_per_chan=None, num_samples_per_event=None, digital=False, has_callback=True,
                 shared_state=None, done_callback=None, use_RSE=True):
        # check inputs
        daq.Task.__init__(self)

        self._log = logging.getLogger('flyvr.daq.IOTask')

        _digital = 'digital' if digital else 'analog'
        self._log.info(f'DAQ:{dev_name}: {_digital}{cha_type}/{cha_ids} (limits: {limits}, '
                       f'SR: {rate}, nSamp/ch: {num_samples_per_chan}, '
                       f'nSamp/event: {num_samples_per_event}, RSE: {use_RSE})')

        self.dev_name = dev_name

        if not isinstance(cha_ids, (list, tuple)):
            cha_ids = [cha_ids]
        if not isinstance(cha_names, (list, tuple)):
            cha_names = [cha_names]

        if cha_names and cha_ids:
            assert len(cha_names) == len(cha_ids)

        self.flyvr_shared_state = shared_state
        assert self.flyvr_shared_state is not None

        # Is this a digital task
        self.digital = digital

        # A function to call on task completion
        self.done_callback = done_callback

        # These are just some dummy values for pass by reference C functions that the NI DAQ api has.
        self.read = daq.int32()
        self.read_float64 = daq.float64()

        self.limits = limits

        self.cha_type = cha_type
        _full_cha_ids = ['%s/%s' % (dev_name, ch) for ch in cha_ids]  # append device name
        self.cha_string = ", ".join(_full_cha_ids)

        self.num_samples_per_chan = num_samples_per_chan
        assert self.num_samples_per_chan is not None
        self.num_samples_per_event = num_samples_per_event
        assert self.num_samples_per_event is not None

        clock_source = None  # use internal clock
        self.callback = None

        self._signal_producer = None

        self._data_generator = None
        self._data_recorders = None

        self._silence_chunk = None  # type: Optional[SampleChunk]
        self._last_chunk = None  # type: Optional[SampleChunk]

        if self.cha_type is "input":
            if not self.digital:
                if use_RSE:
                    self.CreateAIVoltageChan(self.cha_string, "", DAQmx_Val_RSE, -limits, limits, DAQmx_Val_Volts, None)
                else:
                    self.CreateAIVoltageChan(self.cha_string, "", DAQmx_Val_Diff, -limits, limits, DAQmx_Val_Volts,
                                             None)
            else:
                self.CreateDIChan(self.cha_string, "", DAQmx_Val_ChanPerLine)

            # Get the number of channels from the task
            nChans = c_ulong()
            self.GetTaskNumChans(nChans)
            self.num_channels = nChans.value

            if has_callback:
                self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer, self.num_samples_per_event, 0)
                self.CfgInputBuffer(self.num_samples_per_chan * self.num_channels * 4)

        elif self.cha_type is "output":
            if not self.digital:
                self.CreateAOVoltageChan(self.cha_string, "", -limits, limits, DAQmx_Val_Volts, None)
            else:
                self.CreateDOChan(self.cha_string, "", DAQmx_Val_ChanPerLine)

            # Get the number of channels from the task
            nChans = c_ulong()
            self.GetTaskNumChans(nChans)
            self.num_channels = nChans.value

        # We need to create a dataset for log messages.
        if cha_type == "output" and not digital:
            self.flyvr_shared_state.logger.create("/daq/chunk_synchronization_info",
                                                  shape=[2048, SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS],
                                                  maxshape=[None, SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS],
                                                  dtype=np.int64,
                                                  chunks=(2048, SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS))
            self.flyvr_shared_state.logger.log("/daq/chunk_synchronization_info",
                                               int(rate),
                                               attribute_name='sample_rate')
            self.flyvr_shared_state.logger.log("/daq/chunk_synchronization_info",
                                               int(self.num_samples_per_event),
                                               attribute_name='sample_buffer_size')

            for cn, cname in enumerate(SampleChunk.SYNCHRONIZATION_INFO_FIELDS):
                self.flyvr_shared_state.logger.log("/daq/chunk_synchronization_info",
                                                   str(cname),
                                                   attribute_name='column_%d' % cn)

        elif cha_type == "input" and not digital:
            self.samples_dset_name = "/daq/input/samples"
            self.samples_sync_dset_name = "/daq/input/synchronization_info"

            self.flyvr_shared_state.logger.create(self.samples_dset_name,
                                                  shape=[512, self.num_channels],
                                                  maxshape=[None, self.num_channels],
                                                  chunks=(512, self.num_channels),
                                                  dtype=np.float64, scaleoffset=8)
            self.flyvr_shared_state.logger.log(self.samples_dset_name,
                                               int(rate),
                                               attribute_name='sample_rate')
            self.flyvr_shared_state.logger.log(self.samples_dset_name,
                                               int(self.num_samples_per_chan),
                                               attribute_name='sample_buffer_size')
            if cha_names and cha_ids:
                for cn, cname in enumerate(cha_names):
                    self.flyvr_shared_state.logger.log(self.samples_dset_name,
                                                       str(cname),
                                                       attribute_name='column_%d' % cn)

            self.flyvr_shared_state.logger.create(self.samples_sync_dset_name,
                                                  shape=[1024, INPUT_SYNCHRONIZATION_INFO_NUM_FIELDS],
                                                  chunks=(1024, INPUT_SYNCHRONIZATION_INFO_NUM_FIELDS),
                                                  maxshape=[None, INPUT_SYNCHRONIZATION_INFO_NUM_FIELDS],
                                                  dtype=np.int64)
            for cn, cname in enumerate(INPUT_SYNCHRONIZATION_INFO_FIELDS):
                self.flyvr_shared_state.logger.log(self.samples_sync_dset_name,
                                                   str(cname),
                                                   attribute_name='column_%d' % cn)

        elif cha_type == "input" and digital:
            self.samples_dset_name = "/daq/input/digital/samples"
            self.samples_sync_dset_name = "/daq/input/digital/synchronization_info"

            self.flyvr_shared_state.logger.create(self.samples_dset_name,
                                                  shape=[2048, self.num_channels],
                                                  maxshape=[None, self.num_channels],
                                                  chunks=(2048, self.num_channels),
                                                  dtype=np.uint8)
            self.flyvr_shared_state.logger.log(self.samples_dset_name,
                                               int(rate),
                                               attribute_name='sample_rate')
            self.flyvr_shared_state.logger.log(self.samples_dset_name,
                                               int(self.num_samples_per_chan),
                                               attribute_name='sample_buffer_size')

            self.flyvr_shared_state.logger.create(self.samples_sync_dset_name,
                                                  shape=[1024, INPUT_SYNCHRONIZATION_INFO_NUM_FIELDS],
                                                  chunks=(1024, INPUT_SYNCHRONIZATION_INFO_NUM_FIELDS),
                                                  maxshape=[None, INPUT_SYNCHRONIZATION_INFO_NUM_FIELDS],
                                                  dtype=np.float64)
            for cn, cname in enumerate(INPUT_SYNCHRONIZATION_INFO_FIELDS):
                self.flyvr_shared_state.logger.log(self.samples_sync_dset_name,
                                                   str(cname),
                                                   attribute_name='column_%d' % cn)

        if not digital:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels),
                                  dtype=np.float64)  # init empty data array
        else:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.uint8)

        self.CfgSampClkTiming(clock_source, rate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.num_samples_per_chan)
        self.AutoRegisterDoneEvent(0)

        if has_callback:
            self._data_lock = threading.Lock()
            self._newdata_event = threading.Event()
            if self.cha_type is "output":

                cbf = rate / float(self.num_samples_per_event)
                self._log.info('buffer size: %d (buffer callback called every %.3fs, at %.1fHz)' % (
                    self.num_samples_per_event, 1./cbf, cbf))

                self._silence_chunk = SampleChunk.new_silence(
                    np.squeeze(np.zeros((self.num_samples_per_event, self.num_channels), dtype=np.float64)))

                self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Transferred_From_Buffer, self.num_samples_per_event, 0)

                # ensures continuous output and avoids collision of old and new data in buffer
                # self.SetAODataXferReqCond(_full_cha_identifier[0], DAQmx_Val_OnBrdMemEmpty)
                self.SetWriteRegenMode(DAQmx_Val_DoNotAllowRegen)
                self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)

                self.EveryNCallback()  # fill buffer on init
        else:
            self.SetWriteRegenMode(DAQmx_Val_AllowRegen)
            self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)

    def stop(self):
        if self._data_generator is not None:
            self._data = self._data_generator.close()

        if self.data_recorders is not None:
            for data_rec in self.data_recorders:
                data_rec.finish()
                data_rec.close()

    def play_signal_producer_item(self, item):
        if isinstance(self._signal_producer, AudioStimPlaylist):
            try:
                data_generator = self._signal_producer.play_item(item)
                self._log.info('playing playlist item identifier: %s' % item)

                with self._data_lock:
                    chunked_gen = chunker(data_generator, chunk_size=self.num_samples_per_event)
                    self._data_generator = chunked_gen

            except ValueError as _exc:
                self._log.warning('error playing playlist item: %s' % _exc)

    def play_pause(self, pause):
        if isinstance(self._signal_producer, AudioStimPlaylist):
            self._log.info('changing status to paused=%s' % pause)
            self._signal_producer.play_pause(pause=pause)

    def set_signal_producer(self, stim: SignalProducer):
        stim.initialize(BACKEND_DAQ)
        self._signal_producer = stim
        self._log.info('playing AudioStim object: %r' % stim)

        data_generator = stim.data_generator()
        with self._data_lock:
            chunked_gen = chunker(data_generator, chunk_size=self.num_samples_per_event)
            self._data_generator = chunked_gen

    @property
    def data_recorders(self):
        return self._data_recorders

    @data_recorders.setter
    def data_recorders(self, value):

        if value is None:
            self._data_recorders = None

        # We need to store the data recorders as a list internally, because we will iterate over them later
        elif not isinstance(value, list):
            self._data_recorders = [value]

        else:
            self._data_recorders = value

    def send(self, data):
        if self.cha_type == "input":
            raise ValueError("Cannot send on an input channel, it must be an output channel.")

        if self.digital:
            self.WriteDigitalLines(data.shape[0], False, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, data, None,
                                   None)
        else:
            self.WriteAnalogF64(data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, data,
                                daq.byref(self.read), None)

    def EveryNCallback(self):
        with self._data_lock:
            tns = time.time_ns()

            if self.cha_type is "input":
                if not self.digital:
                    self.ReadAnalogF64(DAQmx_Val_Auto, 1.0, DAQmx_Val_GroupByScanNumber,
                                       self._data, self.num_samples_per_chan * self.num_channels, daq.byref(self.read),
                                       None)
                else:
                    numBytesPerSamp = daq.int32()
                    self.ReadDigitalLines(self.num_samples_per_chan, 1.0, DAQmx_Val_GroupByScanNumber,
                                          self._data, self.num_samples_per_chan * self.num_channels,
                                          byref(self.read), byref(numBytesPerSamp), None)

            elif self.cha_type is "output":

                if self._data_generator is None:
                    chunk = self._silence_chunk
                else:
                    chunk = next(self._data_generator)  # type: SampleChunk
                    if chunk is None:
                        chunk = self._silence_chunk

                self._data = chunk.data
                assert (len(self._data) == self.num_samples_per_event)

                if not self.digital:
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

                    self.flyvr_shared_state.logger.log("/daq/chunk_synchronization_info",
                                                       np.array(row, dtype=np.int64))

                    # noinspection DuplicatedCode
                    if chunk_producers_differ(self._last_chunk, chunk):
                        self._log.debug('chunk from new producer: %r' % chunk)
                        self.flyvr_shared_state.signal_new_playlist_item(chunk.producer_identifier, BACKEND_DAQ,
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
                                                                         time_ns=tns)

                    self.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                        self._data, daq.byref(self.read), None)

                    self.flyvr_shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN += self._data.shape[0]
                    self._last_chunk = chunk

                else:
                    self.WriteDigitalLines(self._data.shape[0], False, DAQmx_Val_WaitInfinitely,
                                           DAQmx_Val_GroupByScanNumber, self._data, None, None)

            # send the data to a control if requested.
            if self.data_recorders is not None:
                for data_rec in self.data_recorders:
                    if self._data is not None:
                        data_rec.send((self._data, tns))

            if self.cha_type == "input":
                self.flyvr_shared_state.logger.log(self.samples_dset_name, self._data)

                self.flyvr_shared_state.logger.log(self.samples_sync_dset_name,
                                                   np.array([self.flyvr_shared_state.FICTRAC_FRAME_NUM,
                                                             self.flyvr_shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN,
                                                             self.flyvr_shared_state.DAQ_INPUT_NUM_SAMPLES_READ,
                                                             self.flyvr_shared_state.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN,
                                                             self.flyvr_shared_state.VIDEO_OUTPUT_NUM_FRAMES,
                                                             tns], dtype=np.int64))

                self.flyvr_shared_state.DAQ_INPUT_NUM_SAMPLES_READ += self._data.shape[0]

            self._newdata_event.set()

        return 0  # The function should return an integer

    # noinspection PyUnusedLocal
    def DoneCallback(self, status):

        if self.done_callback is not None:
            self.done_callback(self)

        return 0  # The function should return an integer


# noinspection PyPep8Naming
def io_task_loop(msg_queue: queue.Queue, flyvr_shared_state, options):

    log = logging.getLogger('flyvr.daq')
    log.info('starting DAQ process')

    if len(options.analog_in_channels) < 1:
        log.critical('at least 1 DAQ analog channel must be read - setting to ai0 and continuing')
        input_chans = ["ai0"]
        input_chan_names = ["ai0"]
    else:
        input_chans = ["ai%s" % s for s in sorted(options.analog_in_channels)]
        input_chan_names = [options.analog_in_channels[s] for s in sorted(options.analog_in_channels)]

    analog_out_channels = tuple(sorted(options.analog_out_channels))

    if len(analog_out_channels) > 1:
        raise NotImplementedError('only a single DAQ output channel is supported')

    daq_stim, _ = get_paylist_object(options, playlist_type='daq',
                                     paused_fallback=False,
                                     default_repeat=1,  # repeat=1 is more sensible for DAQ?
                                     attenuator=None)

    if daq_stim is not None:
        try:
            if daq_stim.num_channels != 1:
                raise NotImplementedError('only a single DAQ output channel is supported '
                                          '(yet the playlist has 2 channels of data)')
        except AttributeError:
            log.warning('assuming num_channels=1 from paused playlist')

    is_analog_out = (daq_stim is not None) and len(analog_out_channels) == 1

    sr = int(options.samplerate_daq)
    if daq_stim is not None:
        for s in daq_stim:
            if s.sample_rate != sr:
                raise ValueError('stimulus %r sample rate %s does not match DAQ sample rate %s' % (
                    s, s.sample_rate, sr))

    if sr != DAQ_SAMPLE_RATE_DEFAULT:
        log.warning('changing DAQ sample rate from default %s to %s' % (DAQ_SAMPLE_RATE_DEFAULT, sr))

    # noinspection PyBroadException
    try:

        running = True
        taskAO = None
        taskAI = None

        while running:
            log.info("initializing DAQ Tasks")

            taskAO = None
            if is_analog_out:
                # Get the input and output channels from the options
                output_chans = ["ao" + str(s) for s in analog_out_channels]
                taskAO = IOTask(cha_ids=output_chans, cha_type="output",
                                rate=sr,
                                num_samples_per_chan=DAQ_NUM_OUTPUT_SAMPLES,
                                num_samples_per_event=DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT,
                                shared_state=flyvr_shared_state)

            taskAI = IOTask(cha_ids=input_chans, cha_type="input", cha_names=input_chan_names,
                            rate=sr,
                            num_samples_per_chan=DAQ_NUM_INPUT_SAMPLES,
                            num_samples_per_event=DAQ_NUM_INPUT_SAMPLES_PER_EVENT,
                            shared_state=flyvr_shared_state, use_RSE=options.use_RSE)

            disp_task = ConcurrentTask(task=plot_task_daq, comms="pipe",
                                       taskinitargs=[input_chan_names, taskAI.num_samples_per_chan, 5])

            # Setup the display task to receive messages from recording task.
            taskAI.data_recorders = [disp_task]
            # start disp early so the user sees something
            disp_task.start()

            if taskAO is not None:
                # Setup the stimulus playlist as the data generator
                taskAO.set_signal_producer(daq_stim)

                # Connect AO start to AI start
                taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

            _ = flyvr_shared_state.signal_ready(BACKEND_DAQ)

            if not flyvr_shared_state.wait_for_start():
                log.info('did not receive start signal')
                running = False
                continue

            log.info("starting DAQ tasks")
            if taskAO is not None:
                # Arm the AO task
                # It won't start until the start trigger signal arrives from the AI task
                taskAO.StartTask()

            # Start the AI task
            # This generates the AI start trigger signal and triggers the AO task
            taskAI.StartTask()

            while running:
                try:
                    msg = msg_queue.get(timeout=0.1)
                    if taskAO is not None:
                        if isinstance(msg, AudioStim):
                            taskAO.set_signal_producer(msg)
                        elif isinstance(msg, str):
                            if msg in {'play', 'pause'}:
                                taskAO.play_pause(pause=msg == 'pause')
                            else:
                                taskAO.play_signal_producer_item(msg)

                except queue.Empty:
                    pass

                if flyvr_shared_state.is_stopped():
                    running = False

        log.info('stopped')

        if taskAO is not None:
            taskAO.StopTask()
            taskAO.stop()

        taskAI.StopTask()
        taskAI.stop()

        if taskAO is not None:
            taskAO.ClearTask()

        if taskAI is not None:
            taskAI.ClearTask()

    except Exception:
        flyvr_shared_state.runtime_error(1)


def _ipc_main(q, basedirs):
    pr = PlaylistReciever()
    log = logging.getLogger('flyvr.daq.ipc_main')

    log.debug('starting')

    while True:
        elem = pr.get_next_element()
        if elem:
            # noinspection PyBroadException
            try:
                if 'daq' in elem:
                    stim = stimulus_factory(**elem['daq'], basedirs=basedirs)
                    q.put(stim)
                elif 'daq_item' in elem:
                    q.put(elem['daq_item']['identifier'])
                elif 'daq_action' in elem:
                    q.put(elem['daq_action'])
                else:
                    log.debug("ignoring message: %r" % elem)
            except Exception:
                log.error('could not parse playlist item', exc_info=True)


def run_io(options):
    from flyvr.common import SharedState
    from flyvr.common.logger import DatasetLogServerThreaded

    setup_logging(options)

    q = queue.Queue()
    basedirs = [os.getcwd()]
    if getattr(options, '_config_file_path'):
        # noinspection PyProtectedMember
        basedirs.insert(0, os.path.dirname(options._config_file_path))

    ipc = threading.Thread(daemon=True, name='DAQIpcThread',
                           target=_ipc_main, args=(q, basedirs))
    ipc.start()

    with DatasetLogServerThreaded() as log_server:
        logger = log_server.start_logging_server(options.record_file.replace('.h5', '.daq.h5'))
        state = SharedState(options=options, logger=logger, where=BACKEND_DAQ)
        io_task_loop(q, state, options)


def main_io():
    from flyvr.common.build_arg_parser import build_argparser, parse_options, setup_logging
    from flyvr.audio.util import plot_playlist

    parser = build_argparser()
    parser.add_argument('--plot', action='store_true', help='plot the stimulus playlist')
    options = parse_options(parser.parse_args(), parser)

    if options.plot:
        setup_logging(options)

        if not options.playlist.get('daq'):
            return parser.error('Config file contains no daq playlist')

        plot_playlist(options, 'daq')

        return parser.exit(0)

    run_io(options)
