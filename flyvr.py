import time
import sys
from multiprocessing import freeze_support
from multiprocessing import Value, Array

from audio import io_task
from audio.attenuation import Attenuator
from audio.stimuli import SinStim, AudioStimPlaylist
from common.build_arg_parser import parse_arguments

from common.concurrent_task import ConcurrentTask
from fictrac.fictrac_driver import FicTracDriver
from fictrac.fictrac_driver import fictrac_poll_run_main
from fictrac.fictrac_driver import tracking_update_stub

def main():

    # Create a thread safe Value that specifies the current run state. This will allow
    # us to signal shutdown to multiple processes.
    RUN = Value('i', 1)

    options = parse_arguments()

    # If the user specifies a FicTrac config file, turn on tracking by start the tracking task
    if (options.fictrac_config is not None):

        if options.fictrac_callback is None:
            fictrac_callback = tracking_update_stub

        tracDrv = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                 fictrac_callback, options.pgr_cam_enable)

        # Run the task
        print("Starting FicTrac ... ")
        trackTask = ConcurrentTask(task=fictrac_poll_run_main, comms="pipe", taskinitargs=[tracDrv, RUN])
        trackTask.start()
        time.sleep(2)

    # If the user passed in an attenuation file function, apply it to the playlist
    attenuator = None
    if options.attenuation_file is not None:
        attenuator = Attenuator.load_from_file(options.attenuation_file)
    else:
        print("Warning: No attenuation file specified.")

    # Read the playlist file and create and audio stimulus playlist object
    stimPlaylist = AudioStimPlaylist.fromfilename(options.stim_playlist, options.shuffle, attenuator)

    sys.stdout.write("Initializing DAQ Tasks ... ")
    daqTask = ConcurrentTask(task=io_task.io_task_main, comms="pipe", taskinitargs=[RUN])
    daqTask.start()
    print("Done.")

    sys.stdout.write("Queing playlist ... ")
    daqTask.send(stimPlaylist)
    print("Done")

    # Start the playback and aquistion by sending a start signal.
    daqTask.send(["START", options])

    time.sleep(2)

    # Wait till the user presses enter to end session
    raw_input("Press ENTER to end session ... ")

    print("Shutting down ... ")
    RUN.value = 0;

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