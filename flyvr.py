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

        # Thread safe Value to signal when FicTrac is running an processing frames.
        self.FICTRAC_READY = Value('i', 0)

        # Current FicTrac frame number
        self.FICTRAC_FRAME_NUM = Value('i', 0)

        # Keep track of the current producer for each output channel
        self.OUTPUT_PRODUCER_ID = Array('i', [0] * len(options.analog_out_channels))

def main():

    # Get the arguments passed
    options = parse_arguments()

    # Initialize shared state between processes we are going to spawn
    state = SharedState(options=options)

    # If the user passed in an attenuation file function, apply it to the playlist
    attenuator = None
    if options.attenuation_file is not None:
        attenuator = Attenuator.load_from_file(options.attenuation_file)
    else:
        print("Warning: No attenuation file specified.")

    sys.stdout.write("Initializing DAQ Tasks ... ")
    daqTask = ConcurrentTask(task=io_task.io_task_main, comms="pipe", taskinitargs=[state])
    daqTask.start()
    print("Done.")

    # Read the playlist file and create and audio stimulus playlist object. We pass a callback function to these
    # underlying stimuli that is triggered anytime they generate data. The callback sends a log signal to the
    # master logging process.
    stimPlaylist = AudioStimPlaylist.fromfilename(options.stim_playlist, options.shuffle, attenuator)

    # Start the playback and aquistion by sending a start signal.
    sys.stdout.write("Starting acquisition ... ")
    daqTask.send(["START", options])

    # Wait until we get a ready message from the DAQ task
    while state.DAQ_READY.value == 0:
        time.sleep(0.2)

    print("Done")

    # If the user specifies a FicTrac config file, turn on tracking by start the tracking task
    trackTask = None
    if (options.fictrac_config is not None):

        if options.fictrac_callback is None:
            fictrac_callback = tracking_update_stub

        tracDrv = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                fictrac_callback, options.pgr_cam_enable)

        # Run the task
        print("Starting FicTrac ... ")
        trackTask = ConcurrentTask(task=fictrac_poll_run_main, comms="pipe", taskinitargs=[tracDrv, state])
        trackTask.start()

        # Wait till FicTrac is processing frames
        while state.FICTRAC_READY.value == 0:
            time.sleep(0.2)

    sys.stdout.write("Starting playlist ... ")
    daqTask.send(stimPlaylist)
    print("Done")

    # Wait till the user presses enter to end session
    raw_input("Press ENTER to end session ... ")

    print("Shutting down ... ")
    state.RUN.value = 0;

    # Wait until all the tasks are finnished.
    while daqTask._process.is_alive():
        time.sleep(0.1)

    if trackTask is not None:
        while trackTask._process.is_alive():
            time.sleep(0.1)

    print("Goodbye")

if __name__ == '__main__':
    freeze_support()
    main()