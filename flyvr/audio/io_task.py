# -*- coding: utf-8 -*-
import threading
import time

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

from flyvr.audio.attenuation import Attenuator
from flyvr.audio.signal_producer import chunker, MixedSignal
from flyvr.audio.stimuli import AudioStim, SinStim, AudioStimPlaylist
from flyvr.control.motor_control import BallControlSignal
from flyvr.control.two_photon_control import TwoPhotonController
from flyvr.common.concurrent_task import ConcurrentTask
from flyvr.common.plot_task import plot_task_daq

DAQ_SAMPLE_RATE = 10000
DAQ_NUM_OUTPUT_SAMPLES = 1000
DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT = 50
DAQ_NUM_INPUT_SAMPLES = 10000
DAQ_NUM_INPUT_SAMPLES_PER_EVENT = 10000


# noinspection PyPep8Naming
class IOTask(daq.Task):
    """
    IOTask encapsulates the an input-output task that communicates with the NIDAQ. It works with a list of input or
    output channel names.
    """

    def __init__(self, dev_name="Dev1", cha_name=["ai0"], cha_type="input", limits=10.0, rate=DAQ_SAMPLE_RATE,
                 num_samples_per_chan=DAQ_SAMPLE_RATE, num_samples_per_event=None, digital=False, has_callback=True,
                 shared_state=None, done_callback=None, use_RSE=True):
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

        # A task to send signals to everytime we write a chunk of samples. We will send the current sample number and
        # the current FicTrac frame number
        self.logger = shared_state.logger

        # These are just some dummy values for pass by reference C functions that the NI DAQ api has.
        self.read = daq.int32()
        self.read_float64 = daq.float64()

        self.limits = limits
        self.cha_type = cha_type
        self.cha_name = [dev_name + '/' + ch for ch in cha_name]  # append device name
        self.cha_string = ", ".join(self.cha_name)
        self.num_samples_per_chan = num_samples_per_chan
        self.num_samples_per_event = num_samples_per_event  # self.num_samples_per_chan*self.num_channels

        if self.num_samples_per_event is None:
            self.num_samples_per_event = num_samples_per_chan

        clock_source = None  # use internal clock
        self.callback = None
        self.data_gen = None  # called at start of control
        self._data_recorders = None  # called at end of control

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
            self.logger.create("/fictrac/daq_synchronization_info", shape=[1024, 2], maxshape=[None, 2],
                               dtype=np.int64,
                               chunks=(1024, 2))
        elif cha_type == "input" and not digital:
            self.samples_dset_name = "/input/samples"
            self.samples_time_dset_name = "/input/systemtime"
            self.logger.create(self.samples_dset_name, shape=[512, self.num_channels],
                               maxshape=[None, self.num_channels],
                               chunks=(512, self.num_channels),
                               dtype=np.float64, scaleoffset=8)
            self.logger.create(self.samples_time_dset_name, shape=[1024, 1], chunks=(1024, 1),
                               maxshape=[None, 1], dtype=np.float64)
        elif cha_type == "input" and digital:
            self.samples_dset_name = "/input/digital/samples"
            self.samples_time_dset_name = "/input/digital/systemtime"
            self.logger.create(self.samples_dset_name, shape=[2048, self.num_channels],
                               maxshape=[None, self.num_channels],
                               chunks=(2048, self.num_channels),
                               dtype=np.uint8)
            self.logger.create(self.samples_time_dset_name, shape=[1024, 1], chunks=(1024, 1),
                               maxshape=[None, 1], dtype=np.float64)

        if not digital:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels),
                                  dtype=np.float64)  # init empty data array
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
                # self.SetAODataXferReqCond(self.cha_name[0], DAQmx_Val_OnBrdMemEmpty)
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

        if self.data_recorders is not None:
            for data_rec in self.data_recorders:
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
            systemtime = time.clock()

            # get data from data generator
            if self.data_gen is not None:
                self._sample_chunk = next(self.data_gen)
                self._data = self._sample_chunk.data

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

                # Log output syncrhonization info only if the logger is valid and the task is not digital.
                if self.logger is not None and not self.digital:
                    self.logger.log("/fictrac/daq_synchronization_info",
                                    np.array([self.shared_state.FICTRAC_FRAME_NUM.value,
                                              self.shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.value]))

                if not self.digital:
                    self.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                        self._data, daq.byref(self.read), None)

                    # Keep track of how many samples we have written out in a global variable
                    if self.shared_state is not None:
                        with self.shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.get_lock():
                            self.shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.value += self._data.shape[0]
                else:
                    self.WriteDigitalLines(self._data.shape[0], False, DAQmx_Val_WaitInfinitely,
                                           DAQmx_Val_GroupByScanNumber, self._data, None, None)

            # Send the data to a control if requested.
            if self.data_recorders is not None:
                for data_rec in self.data_recorders:
                    if self._data is not None:
                        data_rec.send((self._data, systemtime))

            # Send the data to our logging process
            if self.logger is not None and self.cha_type == "input":
                self.logger.log(self.samples_dset_name, self._data)
                self.logger.log(self.samples_time_dset_name, np.array([systemtime]))

            self._newdata_event.set()

        return 0  # The function should return an integer

    def DoneCallback(self, status):

        if self.done_callback is not None:
            self.done_callback(self)

        return 0  # The function should return an integer


def setup_playback_callbacks(stim, logger, state):
    """
    This function setups a control function for each stimulus in the playlist to be called when a set of data is
    generated. This control will send a log message to a logging process indicating the amount of samples generated and
    the stimulus that generated them.

    :param stim: The stimulus playlist to setup callbacks on.
    :param logger: The DatasetLogger object to send log signals to.
    :param state: The shared state variable that contains options to the program.
    :return: None
    """

    def make_log_stim_playback(logger, state):
        def callback(event_message):
            logger.log("/output/history",
                       np.array([event_message.metadata['stim_playlist_idx'], event_message.num_samples]))

        return callback

    # Make the control function
    callbacks = make_log_stim_playback(logger, state)

    # Setup the control.
    if isinstance(stim, AudioStim):
        stim.next_event_callbacks = callbacks
    elif isinstance(stim, AudioStimPlaylist):
        for s in stim:
            s.next_event_callbacks = callbacks

    # Lets setup the logging dataset that these log events will be sent to
    logger.create("/output/history",
                  shape=[2048, 2], maxshape=[None, 2],
                  chunks=(2048, 2), dtype=np.int32)


# noinspection PyPep8Naming
def io_task_main(message_pipe, state):
    try:

        taskAO = None
        taskAI = None
        taskDI = None

        options = state.options

        # Check to make sure we are doing analog output
        if options.stim_playlist is None or options.analog_out_channels is None:
            is_analog_out = False
        else:
            is_analog_out = True

        # Check to see if we are doing digital recording
        if options.digital_in_channels is None:
            is_digital_in = False
        else:
            is_digital_in = True

        if is_analog_out:

            # If the user passed in an attenuation file function, apply it to the playlist
            attenuator = None
            if options.attenuation_file is not None:
                attenuator = Attenuator.load_from_file(options.attenuation_file)
            else:
                print("\nWarning: No attenuation file specified.")

            # Read the playlist file and create and audio stimulus playlist object. We will pass a control function to these
            # underlying stimuli that is triggered anytime they generate data. The control sends a log signal to the
            # master logging process.
            audio_stim = AudioStimPlaylist.fromfilename(options.stim_playlist, options.shuffle, attenuator)

            # Make a sanity check, ensure that the number of channels for this audio stimulus matches the number of output
            # channels specified in configuration file.
            if audio_stim.num_channels != len(options.analog_out_channels):
                raise ValueError(
                    "Number of analog output channels specified in config does not equal number specified in playlist!")

        # Keep the daq controller task running until exit is signalled by main thread via RUN shared memory variable
        while state.is_running_well():

            taskAO = None
            if is_analog_out:
                # Get the input and output channels from the options
                output_chans = ["ao" + str(s) for s in options.analog_out_channels]
                taskAO = IOTask(cha_name=output_chans, cha_type="output",
                                num_samples_per_chan=DAQ_NUM_OUTPUT_SAMPLES,
                                num_samples_per_event=DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT,
                                shared_state=state)

            input_chans = ["ai" + str(s) for s in options.analog_in_channels]
            taskAI = IOTask(cha_name=input_chans, cha_type="input",
                            num_samples_per_chan=DAQ_NUM_INPUT_SAMPLES,
                            num_samples_per_event=DAQ_NUM_INPUT_SAMPLES_PER_EVENT,
                            shared_state=state, use_RSE=options.use_RSE)

            taskDO = None
            two_photon_controller = None
            ball_control = None

            # Setup digital control if needed.
            if (options.remote_2P_enable and is_analog_out) or options.ball_control_enable:
                channels = []
                signals = []

                # Setup the two photon control if needed
                if options.remote_2P_enable and is_analog_out:
                    two_photon_controller = TwoPhotonController(start_channel_name=options.remote_start_2P_channel,
                                                                stop_channel_name=options.remote_stop_2P_channel,
                                                                next_file_channel_name=options.remote_next_2P_channel,
                                                                audio_stim_playlist=audio_stim)
                    channels = channels + two_photon_controller.channel_names
                    signals.append(two_photon_controller)

                # Setup the ball control if needed
                if options.ball_control_enable:
                    ball_control = BallControlSignal(periods=options.ball_control_periods,
                                                     durations=options.ball_control_durations,
                                                     loop=options.ball_control_loop,
                                                     sample_rate=DAQ_SAMPLE_RATE)
                    channels.append(options.ball_control_channel)
                    signals.append(ball_control)

                taskDO = IOTask(cha_name=channels, cha_type="output", digital=True,
                                num_samples_per_chan=DAQ_NUM_OUTPUT_SAMPLES,
                                num_samples_per_event=DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT,
                                shared_state=state)

                mixed_signal = MixedSignal(signals)

                # Set the data generator. We will need combine the data generators into one signal for the digital task
                taskDO.set_data_generator(mixed_signal.data_generator())

                # Connect DO start to AI start
                taskDO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

            disp_task = ConcurrentTask(task=plot_task_daq, comms="pipe",
                                       taskinitargs=[input_chans, taskAI.num_samples_per_chan, 5])

            # Setup the display task to receive messages from recording task.
            taskAI.data_recorders = [disp_task]

            # Setup callbacks that will generate log messages to the logging process. These will signal what is playing
            # and when.
            if is_analog_out:
                setup_playback_callbacks(audio_stim, state.logger, state)

            if taskAO is not None:
                # Setup the stimulus playlist as the data generator
                taskAO.set_data_generator(audio_stim.data_generator())

                # Connect AO start to AI start
                taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

            # Setup digital input recording
            if is_digital_in:
                taskDI = IOTask(cha_name=options.digital_in_channels, cha_type="input",
                                digital=True,
                                num_samples_per_chan=DAQ_NUM_INPUT_SAMPLES,
                                num_samples_per_event=DAQ_NUM_INPUT_SAMPLES_PER_EVENT,
                                shared_state=state)

                # Connect DI start to AI start
                taskDI.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

            # Message loop that waits for start signal
            while state.START_DAQ.value == 0 and state.is_running_well():
                time.sleep(0.2)

            # We received the start signal, lets set it back to 0
            state.START_DAQ.value = 0

            # Start the display and logging tasks
            disp_task.start()

            if taskAO is not None:
                # Arm the AO task
                # It won't start until the start trigger signal arrives from the AI task
                taskAO.StartTask()

            # Arm the digital output task
            # It won't start until the start trigger signal arrives from the AI task
            if taskDO is not None:
                taskDO.StartTask()

            # Arm the digital input task
            if taskDI is not None:
                taskDI.StartTask()

            # Start the AI task
            # This generates the AI start trigger signal and triggers the AO task
            taskAI.StartTask()

            # Signal that the DAQ is ready and acquiring samples
            state.DAQ_READY.value = 1

            while state.is_running_well():
                if message_pipe.poll(0.1):
                    try:
                        msg = message_pipe.recv()

                        # If we have received a stimulus object, feed this object to output task for playback
                        if isinstance(msg, AudioStim) | isinstance(msg, AudioStimPlaylist):
                            audio_stim = msg

                            # Setup callbacks that will generate log messages to the logging process. These will signal what is playing
                            # and when.
                            setup_playback_callbacks(audio_stim, state.logger, state)

                            if taskAO is not None:
                                # Setup the stimulus playlist as the data generator
                                taskAO.set_data_generator(msg.data_generator())

                        if isinstance(msg, str) and msg == "STOP":
                            break
                    except:
                        pass

            # stop tasks and properly close callbacks (e.g. flush data to disk and close file)
            if taskAO is not None:
                taskAO.StopTask()
                taskAO.stop()

            taskAI.StopTask()
            taskAI.stop()

            # If we were doing digital output, end that too.
            if taskDO is not None:
                taskDO.StopTask()
                taskDO.stop()
                taskDO.ClearTask()

                # If we were doing digital input, end that too.
            if taskDI is not None:
                taskDI.StopTask()
                taskDI.stop()
                taskDI.ClearTask()

            # If we are doing two photon control, we need to send a special stop signal.
            if two_photon_controller is not None:
                print("Sending 2P imaging stop signal ... ")
                two_photon_controller.send_2P_stop_signal(dev_name=taskDO.dev_name)

        if taskAO is not None:
            taskAO.ClearTask()

        if taskAI is not None:
            taskAI.ClearTask()

        state.DAQ_READY.value = 0

    except Exception as e:
        state.runtime_error(e, -2)


def test_hardware_singlepoint(rate=10000.0):
    taskHandle = daq.TaskHandle()
    samplesPerChannelWritten = daq.int32()
    isLate = daq.c_uint32()

    stim = SinStim(frequency=250, amplitude=1, phase=0, sample_rate=rate, duration=2000, pre_silence=300,
                   post_silence=300)
    chunk_gen = chunker(stim.data_generator(), 100)

    try:
        DAQmxCreateTask("", byref(taskHandle))
        DAQmxCreateAOVoltageChan(taskHandle, "/Dev1/ao0", "", -10.0, 10.0, DAQmx_Val_Volts, None)
        DAQmxCfgSampClkTiming(taskHandle, "", rate, DAQmx_Val_Rising, DAQmx_Val_HWTimedSinglePoint, 100)

        DAQmxStartTask(taskHandle)

        write_index = 0
        while True:
            DAQmxWriteAnalogScalarF64(taskHandle, 1, 10.0, stim.data[write_index], None)
            DAQmxWaitForNextSampleClock(taskHandle, 10, daq.byref(isLate))

            assert isLate.value == 0, "%d" % isLate.value

            write_index += 1

            if write_index >= stim.data.shape[0]:
                write_index = 0

    except daq.DAQError as err:
        print("DAQmx Error: %s" % err)
    finally:
        if taskHandle:
            # DAQmx Stop Code
            DAQmxStopTask(taskHandle)
            DAQmxClearTask(taskHandle)


def main():
    # task2P_DO = IOTask(cha_name=['port0/line0'], cha_type="output", digital=True,
    #                 num_samples_per_chan=50, num_samples_per_event=50)
    #
    # task2P_DO.StartTask()
    #
    # while True:
    #     time.sleep(0.2)

    test_hardware_singlepoint(1000)


if __name__ == "__main__":
    main()
