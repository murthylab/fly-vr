import sys

from common.tools import get_flyvr_git_hash

if sys.version_info[0] < 3:
    raise Exception("FlyVR has been upgraded to require Python 3. If running on setup machine. "
                    "Activate Anaconda conda environment from command line with command 'activate fly_vr_env'")

import numpy as np

import time
from multiprocessing import freeze_support
from multiprocessing import Value, Array

import traceback

from audio import io_task
from audio.attenuation import Attenuator
from audio.stimuli import SinStim, AudioStimPlaylist
from common.build_arg_parser import parse_arguments

from common.concurrent_task import ConcurrentTask
from common.logger import DatasetLogger, DatasetLogServer
from control.callback import FlyVRCallback
from control.threshold_callback import ThresholdCallback

from fictrac.fictrac_driver import FicTracDriver
from fictrac.fictrac_driver import fictrac_poll_run_main


class SharedState(object):
    """
    A class to represent the shared state between our concurrent tasks. We can add values to this shared state and they
    will be passed as an argument to all tasks. This allows us to communicate with thread safe shared variables.
    """
    def __init__(self, options, logger):

        # Lets store the options passed to the program. This does not need to be stored in a thread
        # safe manner.
        self.options = options

        # Create a thread safe Value that specifies the current run state. This will allow
        # us to signal shutdown to multiple processes.
        self.RUN = Value('i', 1)

        # Create a thread safe Value to signal when the DAQ is aquiring samples.
        self.DAQ_READY = Value('i', 0)

        # A variable that communicates to the main DAQ thread to start playback and aquisition
        self.START_DAQ = Value('i', 0)

        # Thread safe Value to signal when FicTrac is running an processing frames.
        self.FICTRAC_READY = Value('i', 0)

        # Current FicTrac frame number
        self.FICTRAC_FRAME_NUM = Value('i', 0)

        # The total number of samples written to the DAQ
        self.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN = Value('i', 0)

        # The total number of samples written to the sound card
        self.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN = Value('i', 0)

        # A value to indicate a runtime error occurred and the program should close. This allows sub-processes to signal
        # to everyone that they have reached an unrepairable state and things need to shutdown.
        self.RUNTIME_ERROR = Value('i', 0)

        # A DatasetLogger object which provides and interface for sending logging messages to the logging process.
        self.logger = logger

    def is_running_well(self):
        return self.RUNTIME_ERROR.value == 0 and self.RUN.value != 0

    def runtime_error(self, excep, error_code):
        sys.stderr.write("RUNTIME ERROR - Unhandled Exception: \n" + str(excep) + "\n")
        traceback.print_exc()
        self.RUN.value = 0
        self.RUNTIME_ERROR.value = -1

def main():

    # Get the arguments passed
    try:
        options = parse_arguments()
    except ValueError as ex:
        sys.stderr.write("Invalid Config Error: \n" + str(ex) + "\n")
        sys.exit(-1)

    try:
        state = None
        daqTask = None
        fictrac_task = None
        log_server = None

        # Setup logging server
        log_server = DatasetLogServer()
        logger = log_server.start_logging_server(options.record_file)

        # Initialize shared state between processes we are going to spawn
        state = SharedState(options=options, logger=logger)

        # Before we do anything, lets store the git hash of the current state of the repo we are running from in the
        # experimental log file.
        # logger.log(dataset_name='/', attribute_name='flyvr_git_hash', obj=get_flyvr_git_hash())

        print("Initializing DAQ Tasks ... ")
        # !!!!!!!!!!!!!!!!
        # Put in code for running LED here
        # Right now using AudioStim function fromfilename to LED out
        daqTask = ConcurrentTask(task=io_task.io_task_main, comms="pipe", taskinitargs=[state])
        daqTask.start()


        print('setup')
        from video.video_server import VideoServer, VideoStreamProxy
        from video.stimuli import LoomingDot
        from time import sleep
        video_server = VideoServer(stimName=options.visual_stimulus,calibration_file=options.calibration_file)
        video_client = video_server.start_stream(frames_per_buffer=128, suggested_output_latency=0.002)
        print('pause...')
        sleep(10)    # takes a bit for the video_server thread to create the psychopy window
        video_client.play(None)
        # print(video_server.getWindow())
        # stim = LoomingDot(window=video_server.getWindow())
        # video_client.play(stim)

        # If the user specifies a FicTrac config file, turn on tracking by start the tracking task
        fictrac_task = None
        tracDrv = None
        if (options.fictrac_config is not None):

            # !!!!!!!!!!!!!!!!!!!!
            # this is where we call the (visual) stimulus
            # it is a Threshold callback because in this case it is supposed to trigger on some
            # fictrac velocity threshold
            fictrac_callback = ThresholdCallback(shared_state=state)

            tracDrv = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                    None, options.pgr_cam_enable,
                                    plot_on=options.fictrac_plot_state)

            # Run the task
            print("Starting FicTrac ... ")
            fictrac_task = ConcurrentTask(task=fictrac_poll_run_main, comms="pipe", taskinitargs=[tracDrv, state])
            fictrac_task.start()

            # Wait till FicTrac is processing frames
            while state.FICTRAC_READY.value == 0 and state.is_running_well():
                time.sleep(0.2)

        if state.is_running_well():

            print(("Delaying start by " + str(options.start_delay) + " ..."))
            time.sleep(options.start_delay)

            # Send a signal to the DAQ to start playback and acquisition
            sys.stdout.write("Starting DAQ tasks ... \n")
            state.START_DAQ.value = 1

            # Wait until we get a ready message from the DAQ task
            while state.DAQ_READY.value == 0 and state.is_running_well():
                time.sleep(0.2)

            # Wait till the user presses enter to end session
            if state.is_running_well():
                input("Press ENTER to end session ... ")

        video_client.close()

    except Exception as e:
        state.runtime_error(e, -1)

    finally:
        print("Shutting down ... ")

        if state is not None:
            state.RUN.value = 0

        # Wait until all the tasks are finished.
        if daqTask is not None:
            while daqTask.process.is_alive():
                time.sleep(0.1)

        if fictrac_task is not None:
            while fictrac_task.process.is_alive():
                time.sleep(0.1)

        if log_server is not None:
            log_server.stop_logging_server()
            log_server.wait_till_close()

        print("Goodbye")

        # Return the RUNTIME_ERROR code as our return value
        return(0)

if __name__ == '__main__':
    freeze_support()
    main()