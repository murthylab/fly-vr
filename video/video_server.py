# import sounddevice as sd

import traceback

import time
import sys
import threading
import multiprocessing
from multiprocessing import Event

import h5py

import numpy as np
import os.path

from video.stimuli import VideoStim, LoomingDot

# from audio.stimuli import SinStim, AudioStim
# from audio.io_task import chunker

import types

from common.concurrent_task import ConcurrentTask
from common.logger import DatasetLogServer

from psychopy import visual, core, event
from psychopy.visual.windowwarp import Warper


# Take a look at audio/sound_server.py. This is a set of classes that implement a client server setup for the audio output to the sound card. You can 
# follow this model I think pretty closely. You can have a VisualServer class whose job it is to kick off a ConcurrentTask object (see SoundServer.start_stream).
# The ConcurrentTask will run a function (or method, see SoundServer._sound_server_main) that handles pushing the graphics to the display. The start_stream
# method also returns another class that implements the client facing API for the server (see SoundStreamProxy). This client API in your case will probably have methods to
# change the stimuli in realtime. The client communicates with the server via a message queue that is setup automatically by ConcurrentTask. These messages can
# be as complicated as you need them to be to implement your API. 


class VideoServer:
    """
    The SoundServer class is a light weight interface  built on top of sounddevice for setting up and playing auditory
    stimulii via a sound card. It handles the configuration of the sound card with low latency ASIO drivers (required to
    be present on the system) and low latency settings. It also tracks information about the number and timing of
    samples be outputed within its device control so synchronization with other data sources in the experiment can be
    made.
    """

    def __init__(self, stimName=None, shared_state=None, calibration_file=None):
        """
        Setup the initial state of the sound server. This does not open any devices for play back. The start_stream
        method must be invoked before playback can begin.
        """


        if stimName is None:
            stimName = 'grating'

        self.stimName = stimName
        # also need the code to set the colors to blue

        self.synchSignal = 0

        self.calibration_file = calibration_file

        # We will update variables related to audio playback in flyvr's shared state data if provided
        self.flyvr_shared_state = shared_state
        self.logger = shared_state.logger

        # No data generator has been set yet
        self._data_generator = None

        # Once, we no the block size and number of channels, we will pre-allocate a block of silence data
        self._silence = None

        # Setup a stream end event, this is how the control will signal to the main thread when it exits.
        self.stream_end_event = multiprocessing.Event()

        # The process we will spawn the video server thread in.
        self.task = ConcurrentTask(task = self._video_server_main, comms='pipe')

        self.logger.create("/video/daq_synchronization_info", shape=[1024, 2], maxshape=[None, 2],
                               dtype=np.int64,
                               chunks=(1024, 2))

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
        if data_generator is None:
            self._data_generator = None
        else:
            self._data_generator = chunker(data_generator, chunk_size=self._stream.blocksize)

    def _play(self, stim):
        """
        Play a video stimulus. This method invokes the data generator of the stimulus to
        generate the data.

        :param stim: An instance of AudioStim or a class that inherits from it.
        :return: None
        """

        # Make sure the user passed and AudioStim instance
        if isinstance(stim, VideoStim):
            self.data_generator = stim.data_generator()
        elif stim is None:
            # self.synchRect = visual.Rect(win=self.mywin, size=(0.25,0.25), pos=[0.5,0.5], lineColor=None, fillColor='grey')
            self.synchRect = visual.Rect(win=self.mywin, size=(0.25,0.25), pos=[0.75,-0.75], lineColor=None, fillColor='grey')
            # self.data_generator = None
            self.yOffset = -0.5
            self.xOffset = 0.2
            # NIVEDITA: this changes stimulus size for movingSquare_OFF
            self.stimSize = 0.25
            self.direction = 1
            self.frameNum = 0
            self.internalCount = 0
            self.countCurrStim = 0
            self.currStim = 0
            if self.stimName == 'grating':
                
                NUM_VIDEO_FIELDS = 7
                # for now fields are:
                # 0: frameNum
                # 1: background color: [-1, 1]
                # 2: object 1: 1 = grating, ...
                # 3: object 1: size
                # 4: object 1: phase
                # 5: object 1: color
                # 6: object 1: phase

                self.sf=50
                self.stimSize = 5
                self.stimColor = -1

                self.screen = visual.GratingStim(win=self.mywin, size=self.stimSize, pos=[0,0], sf=self.sf, color=self.stimColor, phase=0)
                self.logger.create("/video/stimulus", shape=[2048, NUM_VIDEO_FIELDS],
                                                      maxshape=[None, NUM_VIDEO_FIELDS], dtype=np.float64,
                                                      chunks=(2048, NUM_VIDEO_FIELDS))
            elif self.stimName == 'looming_OFF':
                self.screen = visual.Rect(win=self.mywin, size=0.05, pos=[self.xOffset,self.yOffset], lineColor=None, fillColor='black')

                NUM_VIDEO_FIELDS = 7
                # for now fields are:
                # 0: background color: [-1, 1]
                # 1: object 1: 0 = rectangle, 1 = grating, ...
                # 2: object 1: x
                # 3: object 1: y
                # 4: object 1: height
                # 5: object 1: width
                # need to figure out how to log this information in the h5 file (a text field?)

                self.logger.create("/video/stimulus", shape=[2048, NUM_VIDEO_FIELDS],
                                                      maxshape=[None, NUM_VIDEO_FIELDS], dtype=np.float64,
                                                      chunks=(2048, NUM_VIDEO_FIELDS))


            elif self.stimName == 'movingSquare_OFF':
                print('square!')
                self.screen = visual.Rect(win=self.mywin, size=(self.stimSize,self.stimSize), pos=[self.xOffset,self.yOffset], lineColor=None, fillColor='black')
                NUM_VIDEO_FIELDS = 7
                # for now fields are:
                # 0: frameNum
                # 0: background color: [-1, 1]
                # 1: object 1: 0 = rectangle, 1 = grating, ...
                # 2: object 1: height
                # 3: object 1: width
                # 4: object 1: x
                # 5: object 1: y
                # need to figure out how to log this information in the h5 file (a text field?)

                self.logger.create("/video/stimulus", shape=[2048, NUM_VIDEO_FIELDS],
                                                      maxshape=[None, NUM_VIDEO_FIELDS], dtype=np.float64,
                                                      chunks=(2048, NUM_VIDEO_FIELDS))

            elif self.stimName == 'pipStim_OFF':
                print('pipStim!')
                self.yOffset = -0.5
                self.frameNum = 0
                self.screen = visual.Rect(win=self.mywin, size=(0.25,0.25), pos=[self.xOffset,self.yOffset], lineColor=None, fillColor='black')
                f = h5py.File('e:/fly-vr-adam/fly-vr/pipStim.mat','r')
                self.tDis = f['tDis'][:,0]
                self.tAng = f['tAng'][:,0]

                NUM_VIDEO_FIELDS = 7
                # for now fields are:
                # 0: frameNum
                # 0: background color: [-1, 1]
                # 1: object 1: 0 = rectangle, 1 = grating, ...
                # 2: object 1: height
                # 3: object 1: width
                # 4: object 1: x
                # 5: object 1: y
                # need to figure out how to log this information in the h5 file (a text field?)

                self.logger.create("/video/stimulus", shape=[2048, NUM_VIDEO_FIELDS],
                                                      maxshape=[None, NUM_VIDEO_FIELDS], dtype=np.float64,
                                                      chunks=(2048, NUM_VIDEO_FIELDS))

            elif self.stimName == 'dPR1Stim':
                print('dPR1Stim!')
                self.yOffset = -0.25
                self.frameNum = 0
                self.screen = visual.Rect(win=self.mywin, size=(0.25,0.25), pos=[0,self.yOffset], lineColor=None, fillColor='black')
                f = h5py.File('pipStim.mat','r')
                self.tDis = f['tDis'][:,0]
                self.tAng = f['tAng'][:,0]
                self.currStim = 0
                self.countCurrStim = 0
                self.angleOffset = 0

                NUM_VIDEO_FIELDS = 7
                # for now fields are:
                # 0: frameNum
                # 0: background color: [-1, 1]
                # 1: object 1: 0 = rectangle, 1 = grating, ...
                # 2: object 1: height
                # 3: object 1: width
                # 4: object 1: x
                # 5: object 1: y
                # need to figure out how to log this information in the h5 file (a text field?)

                self.logger.create("/video/stimulus", shape=[2048, NUM_VIDEO_FIELDS],
                                                      maxshape=[None, NUM_VIDEO_FIELDS], dtype=np.float64,
                                                      chunks=(2048, NUM_VIDEO_FIELDS))

            elif self.stimName == 'grating_and_moving_switch':
                self.yOffset = 0.25
                # N = 2 seconds
                # what is the logic:
                # N = 5 for how many seconds?
                # N passes of grating alternately moving left and right
                # N passes of square moving left and right
                # square moving randomly in/out?
                # alternate the square being an ON and and OFF stimulus
                self.screen = visual.GratingStim(win=self.mywin, size=5, pos=[0,self.yOffset], sf=50, color=-1)
                NUM_VIDEO_FIELDS = 12
                # for now fields are:
                # 0: frameNum
                # 1: background color: [-1, 1]
                # 2: object 1: 0 = rectangle
                # 3: object 1: height
                # 4: object 1: width
                # 5: object 1: x
                # 6: object 1: y
                # 7: object 1: 1 = grating, ...
                # 8: object 1: size
                # 9: object 1: sf
                # 10: object 1: color
                # 11: object 1: phase
                # need to figure out how to log this information in the h5 file (a text field?)

                self.logger.create("/video/stimulus", shape=[2048, NUM_VIDEO_FIELDS],
                                                      maxshape=[None, NUM_VIDEO_FIELDS], dtype=np.float64,
                                                      chunks=(2048, NUM_VIDEO_FIELDS))

            self.synchRect.draw()
            self.screen.draw()
            self.mywin.update()
            # self.data_generator = stim.data_generator()
        else:
            raise ValueError("The play method of VideoServer only takes instances of VisualStim objects or those that" +
                             "inherit from this base classs. ")

    # def start_stream(self, data_generator=None, num_channels=2, dtype='float32',
    #                 sample_rate=44100, frames_per_buffer=0, suggested_output_latency=0.005):
    def start_stream(self, data_generator=None, num_channels=2, dtype='float32',
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

        # self._stream = None

        # Start the task
        self.task.start()

        return VideoStreamProxy(self)

    def getWindow(self):
        return self.mywin

    def _video_server_main(self, msg_receiver):
        """
        The main process function for the video server. Handles actually setting up the videodevice object\stream.
        Waits to receive objects to play on the stream, sent from other processes using a Queue or Pipe.

        :return: None
        """

        # Initialize number of samples played to 0
        self.samples_played = 0
        # self.mywin = visual.Window([608,684],
        #      useFBO = True)

        # need the code to automatically connect to the projector, set the colors to 7 bits,
        # set the frame rate to be 180 Hz, the projector to blue and the power to the blue LED

        # to some (pre-defined? parameterized?) voltage/amperage
        # traceback.print_stack()

        # create the window for the visual stimulus on the DLP (screen = 1)

        if self.stimName[-4:] == '_OFF':
            self.bgColor = 1
            
        elif self.stimName[-3:] == '_ON':
            self.bgColor = -1
        else:
            self.bgColor = 0.5

        self.mywin = visual.Window([608,684],monitor='DLP',screen=1,
                     useFBO = True, color=self.bgColor)

        if self.calibration_file is not None:
            warpfile = self.calibration_file
        else:
            warpfile = 'calibratedBallImage.data'

        if os.path.isfile(warpfile):
        # warp the image according to some calibration that we have already performed
            self.warper = Warper(self.mywin,
                    # warp='spherical',
                    warp='warpfile',
                    warpfile = "calibratedBallImage.data",
                    warpGridsize = 300,
                    eyepoint = [0.5, 0.5],
                    flipHorizontal = False,
                    flipVertical = False)
        else:
            self.warper = Warper(self.mywin,
                    warp='spherical',
                    warpGridsize = 300,
                    eyepoint = [0.5, 0.5],
                    flipHorizontal = False,
                    flipVertical = False)

        # self.callback_timing_log = np.zeros((self.CALLBACK_TIMING_LOG_SIZE, 5))
        # self.callback_timing_log_index = 0

        # Setup a dataset to store timing information logged from the callback
        # self.timing_log_num_fields = 3
        # self.flyvr_shared_state.logger.create("/fictrac/soundcard_synchronization_info",
        #                                       shape = [2048, self.timing_log_num_fields],
        #                                       maxshape = [None, self.timing_log_num_fields], dtype = np.float64,
        #                                       chunks = (2048, self.timing_log_num_fields))

        # Setup up for playback of silence.
        self.data_generator = None

        # Loop until the stream end event is set.
        # as opposed to the audio, I think what I want to do here is just update the stimulus on 
        # every iteration of the loop
        playingStim = False
        while (not (self.stream_end_event.is_set() and self.flyvr_shared_state is not None and \
                ( self.flyvr_shared_state.is_running_well()))) and \
                (not (self.stream_end_event.is_set())):

            # Pipe.recv() is blocking so let's check first, otherwise we can loop the visual stimulus
            # (the visual stim should eventually probably move to its own thread)
            if msg_receiver.poll():
                # Wait for a message to come
                msg = msg_receiver.recv()
                if isinstance(msg, VideoStim) or msg is None:
                    self._play(msg)
                    playingStim = True
            else:
                if playingStim:
                    # these stimuli need to be turned into classes
                    if self.stimName == 'grating':
                        self.screen.setPhase(0.05,'+')
                        self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                              self.bgColor,
                                              1,
                                              self.sf,
                                              self.stimSize,
                                              self.stimColor,
                                              self.screen.phase[0]]))
                    elif self.stimName == 'looming_OFF':
                        # NIVEDITA: this changes looming speed
                        self.screen.size += 0.01
                        # NIVEDITA: this sets maximum looming size
                        if (self.screen.size > 0.8).any():
                            self.screen.size = (0.05,0.05)

                        self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                      self.bgColor,
                                      0,
                                      self.screen.pos[0],self.screen.pos[1],
                                      self.screen.size[0],self.screen.size[1]]))

                    elif self.stimName == 'movingSquare_OFF':
                        # print('move!')
                        self.screen.pos += [0.01,0]
                        if self.screen.pos[0] >= 1:
                            self.screen.pos[0] = 0

                        self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                      self.bgColor,
                                      0,
                                      self.screen.pos[0],self.screen.pos[1],
                                      self.screen.size[0],self.screen.size[1]]))

                    elif self.stimName == 'pipStim_OFF':
                        self.frameNum += 1
                        # print((self.tAng.shape,self.tDis.shape))
                        # print((self.tAng[self.frameNum]/180,1/self.tDis[self.frameNum]))
                        self.screen.pos =[self.tAng[round(self.frameNum)]/180 + self.xOffset,self.yOffset]
                        self.screen.size = 1/self.tDis[round(self.frameNum)]

                        self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                      self.bgColor,
                                      0,
                                      self.screen.pos[0],self.screen.pos[1],
                                      self.screen.size[0],self.screen.size[1]]))

                    elif self.stimName == 'dPR1Stim':
                        switchStim = 60*20
                        self.frameNum += 1
                        self.countCurrStim += 1
                        if self.countCurrStim > switchStim:
                            self.countCurrStim = 0
                            # currStim: 0,1,2,3 = center, OFF, right, OFF
                            if self.currStim == 0:
                                self.currStim = 1
                                self.angleOffset = -1
                            elif self.currStim == 1:
                                self.currStim = 2
                                self.angleOffset = 0.5
                            elif self.currStim == 2:
                                self.currStim = 3
                                self.angleOffset = -1
                            else:
                                self.currStim = 0
                                self.angleOffset = 0

                        self.screen.pos = [self.angleOffset + self.tAng[round(self.frameNum)]/180,self.yOffset]
                        self.screen.size = 1/self.tDis[round(self.frameNum)]

                        self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                      self.bgColor,
                                      0,
                                      self.screen.pos[0],self.screen.pos[1],
                                      self.screen.size[0],self.screen.size[1]]))

                    elif self.stimName == 'grating_and_moving_switch':
                        # switchStim = 60*2.5*2
                        switchStim = 60*2.5*20
                        internalSwitch = 60*2.5
                        self.frameNum += 1
                        self.countCurrStim += 1
                        self.internalCount += 1

                        if self.countCurrStim > switchStim:
                            self.countCurrStim = 0
                            self.currStim += 1
                            if self.currStim > 3:
                                self.currStim = 0

                            if self.currStim == 0 or self.currStim == 2:
                                self.screen = visual.GratingStim(win=self.mywin, size=5, pos=[0,self.yOffset], sf=50, color=-1)
                            elif self.currStim == 1:
                                # movingDot ON
                                self.mywin.color = -1
                                self.screen = visual.Rect(win=self.mywin, size=(self.stimSize,self.stimSize), pos=[self.xOffset,self.yOffset], lineColor=None, fillColor='white')
                            elif self.currStim == 3:
                                # movingDot OFF
                                self.mywin.color = 1
                                self.screen = visual.Rect(win=self.mywin, size=(self.stimSize,self.stimSize), pos=[self.xOffset,self.yOffset], lineColor=None, fillColor='black')


                            # currStim: 0,1,2,3 = center, OFF, right, OFF

                        if self.internalCount > internalSwitch:
                            self.internalCount = 0
                            self.direction *= -1

                        if self.currStim == 0 or self.currStim == 2:

                            if self.direction > 0:
                                self.screen.setPhase(0.05,'+')
                            else:
                                self.screen.setPhase(0.05,'-')

                            self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                      self.bgColor,
                                      0,
                                      0,0,
                                      0,0,
                                      1,
                                      self.sf,
                                      self.stimSize,
                                      self.stimColor,
                                      self.screen.phase[0]]))

                        if self.currStim == 1 or self.currStim == 3:
                            self.screen.pos += [self.direction*0.01,0]

                            if self.screen.pos[0] >= 1:
                                self.screen.pos[0] = 0
                            elif self.screen.pos[0] <= -1:
                                self.screen.pos[0] = 0

                            self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                      self.bgColor,
                                      0,
                                      self.screen.pos[0],self.screen.pos[1],
                                      self.screen.size[0],self.screen.size[1],
                                      1,
                                      0,
                                      0,
                                      0]))


                        # self.screen = visual.Rect(win=self.mywin, size=0.05, pos=[self.xOffset,self.yOffset], lineColor=None, fillColor='black')


                    elif self.stimName == 'MATfile':
                        pass
                        # print('move!')
                        self.screen.pos += [0.01,0]
                        if self.screen.pos[0] >= 1:
                            self.screen.pos[0] = -1

                        self.logger.log("/video/stimulus",
                                    np.array([self.frameNum,
                                      self.bgColor,
                                      0,
                                      self.screen.pos[0],self.screen.pos[1],
                                      self.screen.size[0],self.screen.size[1]]))

                    if self.synchSignal > 60*10:
                        self.synchRect.fillColor = 'black'
                        self.synchSignal = 0
                    elif self.synchSignal > 60*5:
                        self.synchRect.fillColor = 'white'

                    self.synchSignal += 1
                    self.synchRect.draw()
                    self.screen.draw()
                    self.mywin.update()

                    # only really need to do this every few frames?
                    self.logger.log("/video/daq_synchronization_info",
                                    np.array([self.frameNum,
                                              self.flyvr_shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.value]))




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

            # Make sure all is good in the rest of the application
            if not self.flyvr_shared_state.is_running_well():
                raise sd.CallbackStop()

            try:

                # If we have no data generator set, then play silence. If not, call its next method
                if self._data_generator is None:
                    producer_id = -1 # Lets code silence as -1
                    data = self._silence
                else:
                    data_chunk = next(self._data_generator)
                    producer_id = data_chunk.producer_id
                    data = data_chunk.data.data

                # Make extra sure the length of the data we are getting is the correct number of samples
                assert(len(data) == frames)

            except StopIteration:
                print('Audio generator produced StopIteration, something went wrong! Aborting playback', file=sys.stderr)
                raise sd.CallbackAbort

            # Lets keep track of some running information
            self.samples_played = self.samples_played + frames

            # Update the number of samples played in the shared state counter


            #self.flyvr_shared_state.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN.value += frames

            if len(data) < len(outdata):
                outdata.fill(0)
                raise sd.CallbackStop
            else:

                if data.ndim == 1 and self._num_channels == 2:
                    outdata[:, 0] = data
                    outdata[:, 1] = data
                else:
                    outdata[:] = data

        return callback

class VideoStreamProxy:
    """
    The VideoStreamProxy class acts as an interface to a SoundServer object that is running on another process. It
    handles sending commands to the object on the other process.
    """

    def __init__(self, video_server):
        """
        Initialize the SoundStreamProxy with an already setup SoundServer object. This assummes that the server is
        running and ready to receive commands.

        :param sound_server: The SoundServer object to issue commands to.
        """
        self.video_server = video_server
        self.task = self.video_server.task

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
        self.video_server.stream_end_event.set()

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
    stim1 = LoomingDot(param1=200, param2=1.0)
    stims = [stim1, None]

    # Setup logging server
    log_server = DatasetLogServer()
    logger = log_server.start_logging_server("test.h5")

    shared_state = SharedState(None, logger)

    video_server = VideoServer(flyvr_shared_state=shared_state)
    video_client = video_server.start_stream(frames_per_buffer=CHUNK_SIZE, suggested_output_latency=0.002)

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