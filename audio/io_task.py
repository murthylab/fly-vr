# -*- coding: utf-8 -*-
import sys
import threading
import time

import PyDAQmx as daq
from PyDAQmx.DAQmxCallBack import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxFunctions import *

import numpy as np

from common.concurrent_task import ConcurrentTask
from audio.stimuli import AudioStim, SinStim, AudioStimPlaylist
from common.plot_task import plot_task_main
from common.log_task import log_audio_task_main

class IOTask(daq.Task):
    """
    IOTask encapsulates the an input-output task that communicates with the NIDAQ. It works with a list of input or
    output channel names.
    """
    def __init__(self, dev_name="Dev1", cha_name=["ai0"], limits=10.0, rate=10000.0):
        # check inputs
        daq.Task.__init__(self)
        assert isinstance(cha_name, list)

        self.limits=limits
        self.read = daq.int32()
        self.read_float64 = daq.float64()
        cha_types = {"i": "input", "o": "output"}
        self.cha_type = [cha_types[cha[1]] for cha in cha_name]
        self.cha_name = [dev_name + '/' + ch for ch in cha_name]  # append device name
        self.cha_string = ", ".join(self.cha_name)
        self.num_channels = len(cha_name)

        clock_source = None  # use internal clock
        # FIX: input and output tasks can have different sizes
        self.callback = None
        self.data_gen = None  # called at start of callback
        self.data_rec = None  # called at end of callback
        if self.cha_type[0] is "input":
            self.num_samples_per_chan = 10000
            self.num_samples_per_event = 10000  # self.num_samples_per_chan*self.num_channels
            self.CreateAIVoltageChan(self.cha_string, "", DAQmx_Val_RSE, -limits, limits, DAQmx_Val_Volts, None)
            self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer, self.num_samples_per_event, 0)
            self.CfgInputBuffer(self.num_samples_per_chan * self.num_channels * 4)
        elif self.cha_type[0] is "output":
            self.num_samples_per_chan = 5000
            self.num_samples_per_event = 50  # determines shortest interval at which new data can be generated
            self.CreateAOVoltageChan(self.cha_string, "", -limits, limits, DAQmx_Val_Volts, None)
            self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Transferred_From_Buffer, self.num_samples_per_event, 0)
            self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)
            # ensures continuous output and avoids collision of old and new data in buffer
            self.SetWriteRegenMode(DAQmx_Val_DoNotAllowRegen)
        self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.float64)  # init empty data array
        self.CfgSampClkTiming(clock_source, rate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.num_samples_per_chan)
        self.AutoRegisterDoneEvent(0)
        self._data_lock = threading.Lock()
        self._newdata_event = threading.Event()
        if self.cha_type[0] is "output":
            self.EveryNCallback()  # fill buffer on init

    def stop(self):
        if self.data_gen is not None:
            self._data = self.data_gen.close()  # close data generator
        if self.data_rec is not None:
            for data_rec in self.data_rec:
                data_rec.finish()
                data_rec.close()

    @property
    def data_generator(self):
        """
        Get the data generator for output

        :return: A generator of 1D numpy.ndarray of data.
        """
        return self.data_gen

    @data_generator.setter
    def data(self, data_generator):
        """
        Set the data generator for the audio stimulus directly.

        :param data_generator: A generator function of audio data.
        """
        with self._data_lock:
            self.data_gen = data_generator

    # FIX: different functions for AI and AO task types instead of in-function switching?
    #      or maybe pass function handle?
    def EveryNCallback(self):
        with self._data_lock:
            systemtime = time.clock()
            if self.data_gen is not None:
                self._data = self.data_gen.next()  # get data from data generator
            if self.cha_type[0] is "input":
                self.ReadAnalogF64(DAQmx_Val_Auto, 1.0, DAQmx_Val_GroupByScanNumber,
                                   self._data, self.num_samples_per_chan * self.num_channels, daq.byref(self.read), None)
            elif self.cha_type[0] is "output":
                self.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel,
                                    self._data, daq.byref(self.read), None)
            if self.data_rec is not None:
                for data_rec in self.data_rec:
                    if self._data is not None:
                        data_rec.send((self._data, systemtime))
            self._newdata_event.set()
        return 0  # The function should return an integer

    def DoneCallback(self, status):
        print("Done status", status)
        return 0  # The function should return an integer

def io_task_main(message_pipe):

    while True:
        # CONFIGURABLE
        RUN = False
        while RUN is False:
            if message_pipe.poll(0.1):
                try:
                    msg = message_pipe.recv()

                    # If we have received a stimulus object, feed this object to output task for playback
                    if isinstance(msg, AudioStim) | isinstance(msg, AudioStimPlaylist):
                        taskAO.data_generator = msg.data_generator
                    elif isinstance(msg, list):
                        command = msg[0]
                        options = msg[1]
                        args = msg[2]
                        if command == "START":
                            RUN = True
                except:
                    pass

        # Get the input and output channels from the options
        output_chans = ["ao" + str(s) for s in options.analog_out_channels]
        input_chans = ["ai" + str(s) for s in options.analog_in_channels]

        taskAO = IOTask(cha_name=output_chans)
        taskAI = IOTask(cha_name=input_chans)

        disp_task = ConcurrentTask(task=plot_task_main, comms="pipe", taskinitargs=[int(options.display_input_channel)])
        disp_task.start()
        save_task = ConcurrentTask(task=log_audio_task_main, comms="queue", taskinitargs=[options.record_file, len(input_chans)])
        save_task.start()

        taskAI.data_rec = [disp_task, save_task]

        # Connect AO start to AI start
        taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

        sys.stdout.write("Starting DAQ Tasks ... ")
        # Arm the AO task
        # It won't start until the start trigger signal arrives from the AI task
        taskAO.StartTask()

        # Start the AI task
        # This generates the AI start trigger signal and triggers the AO task
        taskAI.StartTask()
        print("Done")

        while RUN:
            time.sleep(1)
            if message_pipe.poll(0.1):
                try:
                    msg = message_pipe.recv()
                    if msg == "STOP":
                        RUN = False

                    # If we have received a stimulus object, feed this object to output task for playback
                    if isinstance(msg, AudioStim) | isinstance(msg, AudioStimPlaylist):
                        taskAO.data_generator = msg.data_generator
                except:
                    pass

        # stop tasks and properly close callbacks (e.g. flush data to disk and close file)
        taskAO.StopTask()
        taskAO.stop()
        taskAI.StopTask()
        taskAI.stop()

    taskAO.ClearTask()
    taskAI.ClearTask()