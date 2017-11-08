import time
import sys
from multiprocessing import freeze_support
from multiprocessing import Value, Array

import h5py


from audio import io_task
from audio.attenuation import Attenuator
from audio.stimuli import SinStim, AudioStimPlaylist
from common.build_arg_parser import parse_arguments

from common.concurrent_task import ConcurrentTask
from fictrac.fictrac_driver import FicTracDriver
from fictrac.fictrac_driver import fictrac_poll_run_main
from fictrac.fictrac_driver import tracking_update_stub


class SharedState(object):
    """
    A class to represent the shared state between our concurrent tasks. We can add values to this shared state and they
    will be passed as an argument to all tasks. This allows us to communicate with thread safe shared variables.
    """
    def __init__(self, options):

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

        self.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN = Value('i', 0)

        # A value to indicate a runtime error occurred and the program should close. This allows sub-processes to signal
        # to everyone that they have reached an unrepairable state and things need to shutdown.
        self.RUNTIME_ERROR = Value('i', 0)

    def is_running_well(self):
        return self.RUNTIME_ERROR.value == 0 and self.RUN.value != 0

    def runtime_error(self, excep, error_code):
        sys.stderr.write("RUNTIME ERROR - Unhandled Exception: \n" + str(excep) + "\n")
        self.RUN.value = 0
        self.RUNTIME_ERROR.value = -1


def main():

    try:
        state = None
        daqTask = None
        fictrac_task = None

        # Get the arguments passed
        options = parse_arguments()

        # Initialize shared state between processes we are going to spawn
        state = SharedState(options=options)

        print("Initializing DAQ Tasks ... ")
        daqTask = ConcurrentTask(task=io_task.io_task_main, comms="pipe", taskinitargs=[state])
        daqTask.start()

        # If the user specifies a FicTrac config file, turn on tracking by start the tracking task
        fictrac_task = None
        if (options.fictrac_config is not None):

            if options.fictrac_callback is None:
                fictrac_callback = tracking_update_stub
            else:
                fictrac_callback = options.fictrac_callback

            tracDrv = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                    fictrac_callback, options.pgr_cam_enable)

            # Run the task
            print("Starting FicTrac ... ")
            fictrac_task = ConcurrentTask(task=fictrac_poll_run_main, comms="pipe", taskinitargs=[tracDrv, state])
            fictrac_task.start()

            # Wait till FicTrac is processing frames
            while state.FICTRAC_READY.value == 0 and state.is_running_well():
                time.sleep(0.2)

        if state.is_running_well():

            print("Delaying start by " + str(options.start_delay) + " ...")
            time.sleep(options.start_delay)

            # Send a signal to the DAQ to start playback and acquisition
            sys.stdout.write("Starting playback and acquisition ... \n")
            state.START_DAQ.value = 1

            # Wait until we get a ready message from the DAQ task
            while state.DAQ_READY.value == 0 and state.is_running_well():
                time.sleep(0.2)

            # Wait till the user presses enter to end session
            if state.is_running_well():
                raw_input("Press ENTER to end session ... ")

    except Exception, e:
        state.runtime_error(e, -1)

    finally:
        print("Shutting down ... ")

        if state is not None:
            state.RUN.value = 0

        # Wait until all the tasks are finnished.
        if daqTask is not None:
            while daqTask._process.is_alive():
                time.sleep(0.1)

        if fictrac_task is not None:
            while fictrac_task._process.is_alive():
                time.sleep(0.1)

        print("Goodbye")

        # Return the RUNTIME_ERROR code as our return value
        return(0)

if __name__ == '__main__':
    freeze_support()
    main()