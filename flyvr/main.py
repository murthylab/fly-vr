import sys

if sys.version_info[0] < 3:
    raise Exception("FlyVR has been upgraded to require Python 3. If running on setup machine. "
                    "Activate Anaconda conda environment from command line with command 'activate fly_vr_env'")

import time
import traceback
from multiprocessing import freeze_support

import numpy as np

from flyvr.audio import io_task
from flyvr.audio.attenuation import Attenuator
from flyvr.audio.stimuli import SinStim, AudioStimPlaylist
from flyvr.common import SharedState
from flyvr.common.build_arg_parser import parse_arguments
from flyvr.common.concurrent_task import ConcurrentTask
from flyvr.common.logger import DatasetLogger, DatasetLogServer
from flyvr.common.tools import get_flyvr_git_hash
from flyvr.control.callback import FlyVRCallback
from flyvr.control.threshold_callback import ThresholdCallback
from flyvr.fictrac.fictrac_driver import FicTracDriver, fictrac_poll_run_main
from flyvr.fictrac.replay import FicTracDriverReplay


def main_launcher():
    freeze_support()

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
        from flyvr.video.video_server import VideoServer, VideoStreamProxy
        from flyvr.video.stimuli import LoomingDot
        from time import sleep
        video_server = VideoServer(stimName=options.visual_stimulus,calibration_file=options.screen_calibration,shared_state=state)
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

            if options.fictrac_config.endswith('.h5'):
                tracDrv = FicTracDriverReplay(options.fictrac_config)
            else:
                tracDrv = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                        pgr_enable=options.pgr_cam_enable)

            # Run the task
            print("Starting FicTrac ... ")
            fictrac_task = ConcurrentTask(task=fictrac_poll_run_main, comms="pipe", taskinitargs=[tracDrv, state])
            fictrac_task.start()

            # Wait till FicTrac is processing frames
            while state.FICTRAC_READY == 0 and state.is_running_well():
                time.sleep(0.2)

        if state.is_running_well():

            print(("Delaying start by " + str(options.start_delay) + " ..."))
            time.sleep(options.start_delay)

            # Send a signal to the DAQ to start playback and acquisition
            sys.stdout.write("Starting DAQ tasks ... \n")
            state.START_DAQ = 1

            # Wait until we get a ready message from the DAQ task
            while state.DAQ_READY == 0 and state.is_running_well():
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
            state.RUN = 0

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

