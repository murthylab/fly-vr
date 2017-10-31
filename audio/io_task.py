# -*- coding: utf-8 -*-
import sys
import threading
import time

import PyDAQmx as daq
from PyDAQmx.DAQmxCallBack import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxFunctions import *

import numpy as np

import common.tools
from audio.attenuation import Attenuator

from audio.signal_producer import chunker, SampleChunk

from common.concurrent_task import ConcurrentTask
from audio.stimuli import AudioStim, SinStim, AudioStimPlaylist
from common.plot_task import plot_task_main
from common.log_task import log_audio_task_main
from two_photon.two_photon_control import TwoPhotonController

NUM_OUTPUT_SAMPLES = 400
NUM_OUTPUT_SAMPLES_PER_EVENT = 50


class IOTask(daq.Task):
    """
    IOTask encapsulates the an input-output task that communicates with the NIDAQ. It works with a list of input or
    output channel names.
    """
    def __init__(self, dev_name="Dev1", cha_name=["ai0"], cha_type="input", limits=10.0, rate=10000.0,
                 num_samples_per_chan=10000, num_samples_per_event=None, digital=False, has_callback=True,
                 shared_state=None, done_callback=None):
        # check inputs
        daq.Task.__init__(self)

        self.dev_name = dev_name

        if not isinstance(cha_name, list):
            cha_name = [cha_name]

        # If a shared_state object was passed in, store it in the class
        self.shared_state = shared_state

        # Is this a digital task
        self.digital = digital

        # A function to call on task completion
        self.done_callback = done_callback

        # These are just some dummy values for pass by reference C functions that the NI DAQ api has.
        self.read = daq.int32()
        self.read_float64 = daq.float64()

        self.limits=limits
        self.cha_type = cha_type
        self.cha_name = [dev_name + '/' + ch for ch in cha_name]  # append device name
        self.cha_string = ", ".join(self.cha_name)
        self.num_channels = len(cha_name)
        self.num_samples_per_chan = num_samples_per_chan
        self.num_samples_per_event = num_samples_per_event  # self.num_samples_per_chan*self.num_channels

        if self.num_samples_per_event is None:
            self.num_samples_per_event = num_samples_per_chan

        clock_source = None  # use internal clock
        self.callback = None
        self.data_gen = None  # called at start of callback
        self.data_rec = None  # called at end of callback

        if self.cha_type is "input":
            if not self.digital:
                self.CreateAIVoltageChan(self.cha_string, "", DAQmx_Val_RSE, -limits, limits, DAQmx_Val_Volts, None)
            else:
                self.CreateDIChan(self.cha_string, "", daq.DAQmx_Val_ChanPerLine)

            if has_callback:
                self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer, self.num_samples_per_event, 0)
                self.CfgInputBuffer(self.num_samples_per_chan * self.num_channels * 4)

        elif self.cha_type is "output":
            if not self.digital:
                self.CreateAOVoltageChan(self.cha_string, "", -limits, limits, DAQmx_Val_Volts, None)
            else:
                self.CreateDOChan(self.cha_string, "", daq.DAQmx_Val_ChanPerLine)

        if not digital:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.float64)  # init empty data array
        else:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.uint8)

        # Since this data did not come from a sample chunk object, set it to None
        self._sample_chunk = None

        self.CfgSampClkTiming(clock_source, rate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.num_samples_per_chan)
        self.AutoRegisterDoneEvent(0)

        if has_callback:
            self._data_lock = threading.Lock()
            self._newdata_event = threading.Event()
            if self.cha_type is "output":

                self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Transferred_From_Buffer, self.num_samples_per_event, 0)
                # ensures continuous output and avoids collision of old and new data in buffer
                #self.SetAODataXferReqCond(self.cha_name[0], DAQmx_Val_OnBrdMemEmpty)
                self.SetWriteRegenMode(DAQmx_Val_DoNotAllowRegen)
                self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)

                self.EveryNCallback()  # fill buffer on init
        else:
            self.SetWriteRegenMode(DAQmx_Val_AllowRegen)
            self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)

        # if self.cha_type == "output":
        #     tranCond = daq.int32()
        #     self.GetAODataXferReqCond(self.cha_name[0], daq.byref(tranCond))
        #     print("Channel Type:" + self.cha_type + ", Transfer Cond: " + str(tranCond))

    def stop(self):
        if self.data_gen is not None:
            self._data = self.data_gen.close()  # close data generator

        if self.data_rec is not None:
            for data_rec in self.data_rec:
                data_rec.finish()
                data_rec.close()

    def set_data_generator(self, data_generator):
        """
        Set the data generator for the audio stimulus directly.

        :param data_generator: A generator function of audio data.
        """
        with self._data_lock:
            chunked_gen = chunker(data_generator, chunk_size=self.num_samples_per_chan)
            self.data_gen = chunked_gen

    def send(self, data):
        if self.cha_type == "input":
            raise ValueError("Cannot send on an input channel, it must be an output channel.")
        if self.digital:
            self.WriteDigitalLines(data.shape[0], False, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, data, None, None)
        else:
            self.WriteAnalogF64(data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, data, daq.byref(self.read), None)

    def EveryNCallback(self):
        with self._data_lock:
            systemtime = time.clock()

            # get data from data generator
            if self.data_gen is not None:
                self._sample_chunk = self.data_gen.next()
                self._data = self._sample_chunk.data
            if self.cha_type is "input":
                if not self.digital:
                    self.ReadAnalogF64(DAQmx_Val_Auto, 1.0, DAQmx_Val_GroupByScanNumber,
                                   self._data, self.num_samples_per_chan * self.num_channels, daq.byref(self.read), None)
                else:
                    numBytesPerSamp = daq.int32()
                    self.ReadDigitalLines(self.num_samples_per_chan, 1.0, DAQmx_Val_GroupByScanNumber,
                                          self._data, self.num_samples_per_chan * self.num_channels,
                                          byref(self.read),  byref(numBytesPerSamp), None)

            elif self.cha_type is "output":
                if not self.digital:
                    self.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                    self._data, daq.byref(self.read), None)
                else:
                    self.WriteDigitalLines(self._data.shape[0], False, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber, self._data, None, None)

            # Send the data to a callback if requested.
            if self.data_rec is not None:
                for data_rec in self.data_rec:
                    if self._data is not None:
                        data_rec.send((self._data, systemtime))

            self._newdata_event.set()
        return 0  # The function should return an integer

    def DoneCallback(self, status):

        if self.done_callback is not None:
            self.done_callback(self)

        return 0  # The function should return an integer

@common.tools.coroutine
def data_generator_test(channels=1, num_samples=10000, dtype=np.float64):
    '''generator yields next chunk of data for output'''
    # generate all stimuli

    max_value = 5

    if dtype == np.uint8:
        max_value = 1

    data = list()
    for ii in range(2):
        # t = np.arange(0, 1, 1.0 / max(100.0 ** ii, 100))
        # tmp = np.tile(0.2 * np.sin(5000 * t).astype(np.float64), (channels, 1)).T

        # simple ON/OFF pattern
        tmp = max_value * ii * np.ones((channels, num_samples)).astype(dtype).T
        data.append(np.ascontiguousarray(tmp))  # `ascont...` necessary since `.T` messes up internal array format
    count = 0  # init counter
    try:
        while True:
            count += 1
            # print("{0}: generating {1}".format(count, data[(count-1) % len(data)].shape))
            yield SampleChunk(producer_id=0, data=data[(count - 1) % len(data)])
    except GeneratorExit:
        print("   cleaning up datagen.")

def setup_playback_callbacks(stim, log_task):
    def make_log_stim_playback(log_task_msg_queue):
        def callback(event_message):
            log_task_msg_queue.send(event_message)

        return callback

    callbacks = make_log_stim_playback(log_task)

    if isinstance(stim, AudioStim):
        stim.next_event_callbacks = callbacks
    elif isinstance(stim, AudioStimPlaylist):
        for s in stim.stims:
            s.next_event_callbacks = callbacks

def io_task_main(message_pipe, state):

    options = state.options

    # If the user passed in an attenuation file function, apply it to the playlist
    attenuator = None
    if state.options.attenuation_file is not None:
        attenuator = Attenuator.load_from_file(options.attenuation_file)
    else:
        print("\nWarning: No attenuation file specified.")

    # Read the playlist file and create and audio stimulus playlist object. We will pass a callback function to these
    # underlying stimuli that is triggered anytime they generate data. The callback sends a log signal to the
    # master logging process.
    audio_stim = AudioStimPlaylist.fromfilename(options.stim_playlist, options.shuffle, attenuator)

    # Keep the daq controller task running until exit is signalled by main thread via RUN shared memory variable
    while state.RUN.value != 0:

        # Get the input and output channels from the options
        output_chans = ["ao" + str(s) for s in options.analog_out_channels]
        input_chans = ["ai" + str(s) for s in options.analog_in_channels]

        taskAO = IOTask(cha_name=output_chans, cha_type="output",
                        num_samples_per_chan=NUM_OUTPUT_SAMPLES, num_samples_per_event=NUM_OUTPUT_SAMPLES_PER_EVENT,
                        shared_state=state)
        taskAI = IOTask(cha_name=input_chans, cha_type="input",
                        num_samples_per_chan=10000, num_samples_per_event=10000,
                        shared_state=state)

        # Setup the two photon control if needed
        two_photon_control = None
        taskDO = None
        if state.options.remote_2P_enable:
            two_photon_controller = TwoPhotonController(start_channel_name=state.options.remote_start_2P_channel,
                                                        stop_channel_name=state.options.remote_stop_2P_channel,
                                                        next_file_channel_name=state.options.remote_next_2P_channel,
                                                        audio_stim_playlist=audio_stim)
            taskDO = IOTask(cha_name=two_photon_controller.channel_names, cha_type="output", digital=True,
                            num_samples_per_chan=NUM_OUTPUT_SAMPLES, num_samples_per_event=NUM_OUTPUT_SAMPLES_PER_EVENT,
                            shared_state=state)

            taskDO.set_data_generator(two_photon_controller.data_generator())

            # Connect DO start to AI start
            taskDO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

        disp_task = ConcurrentTask(task=plot_task_main, comms="pipe",
                                   taskinitargs=[input_chans,taskAI.num_samples_per_chan,10])
        save_task = ConcurrentTask(task=log_audio_task_main, comms="queue", taskinitargs=[state])

        taskAI.data_rec = [disp_task, save_task]

        setup_playback_callbacks(audio_stim, save_task)
        taskAO.set_data_generator(audio_stim.data_generator())

        # Connect AO start to AI start
        taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

        # Message loop that waits for start signal
        while state.START_DAQ.value == 0:
            time.sleep(0.2)

        # We received the start signal, lets set it back to 0
        state.START_DAQ.value = 0

        # Start the display and logging tasks
        disp_task.start()
        save_task.start()

        # Arm the AO task
        # It won't start until the start trigger signal arrives from the AI task
        taskAO.StartTask()

        # Arm the DO task
        # It won't start until the start trigger signal arrives from the AI task
        taskDO.StartTask()

        # Start the AI task
        # This generates the AI start trigger signal and triggers the AO task
        taskAI.StartTask()

        # Signal that the DAQ is ready and acquiring samples
        state.DAQ_READY.value = 1

        while state.RUN.value != 0:
            if message_pipe.poll(0.1):
                try:
                    msg = message_pipe.recv()

                    # If we have received a stimulus object, feed this object to output task for playback
                    if isinstance(msg, AudioStim) | isinstance(msg, AudioStimPlaylist):
                        audio_stim = msg

                        setup_playback_callbacks(audio_stim, save_task)

                        taskAO.set_data_generator(msg.data_generator())
                    if isinstance(msg, str) and msg == "STOP":
                        break
                except:
                    pass

        # stop tasks and properly close callbacks (e.g. flush data to disk and close file)
        taskAO.StopTask()
        taskAO.stop()

        taskAI.StopTask()
        taskAI.stop()

        # If we were doing digital output, end that too.
        if taskDO is not None:
            print("Sending 2P imaging stop signal ... ")
            taskDO.StopTask()
            taskDO.stop()
            taskDO.ClearTask()
            two_photon_controller.send_2P_stop_signal(dev_name=taskDO.dev_name)

    taskAO.ClearTask()
    taskAI.ClearTask()

    state.DAQ_READY.value = 0

def test_hardware_singlepoint(rate=1000.0, chunk_size=100):
    taskHandle = TaskHandle()
    samplesPerChannelWritten = daq.int32()
    isLate = daq.c_uint32()

    stim = SinStim(frequency=250, amplitude=1, phase=0, sample_rate=rate, duration=2000, pre_silence=300, post_silence=300)
    chunk_gen = chunker(stim.data_generator(), 100)

    try:
        DAQmxCreateTask("", byref(taskHandle))
        DAQmxCreateAOVoltageChan(taskHandle, "/Dev1/ao0", "", -10.0, 10.0, DAQmx_Val_Volts, None)
        DAQmxCfgSampClkTiming(taskHandle, "", rate, DAQmx_Val_Rising, DAQmx_Val_HWTimedSinglePoint, stim.data.shape[0])

        DAQmxStartTask(taskHandle)

        for i in xrange(stim.data.shape[0]/chunk_size):
            DAQmxWriteAnalogF64(taskHandle, chunk_size, 1, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel,
                                chunk_gen.next(), daq.byref(samplesPerChannelWritten), None)
            DAQmxWaitForNextSampleClock(taskHandle, 10, daq.byref(isLate))
            assert isLate.value == 0, "%d" % isLate.value

    except DAQError as err:
        print "DAQmx Error: %s" % err
    finally:
        if taskHandle:
            # DAQmx Stop Code
            DAQmxStopTask(taskHandle)
            DAQmxClearTask(taskHandle)

def main():
   pass

if __name__ == "__main__":
    main()
