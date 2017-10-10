import time
import sys
from multiprocessing import freeze_support

from audio import io_task
from audio.attenuation import Attenuator
from audio.stimuli import SinStim, AudioStimPlaylist
from common.build_arg_parser import parse_arguments

from common.concurrent_task import ConcurrentTask
from fictrac.fictrac_driver import FicTracDriver

def main():

    options = parse_arguments()

    # If the user passed in an attenuation file function, apply it to the playlist
    attenuator = None
    if options.attenuation_file is not None:
        attenuator = Attenuator.load_from_file(options.attenuation_file)
    else:
        print("Warning: No attenuation file specified.")

    # Read the playlist file and create and audio stimulus playlist object
    stimPlaylist = AudioStimPlaylist.fromfilename(options.stim_playlist, options.shuffle, attenuator)

    sys.stdout.write("Initializing DAQ Tasks ... ")
    daqTask = ConcurrentTask(task=io_task.io_task_main, comms="pipe", taskinitargs=[])
    daqTask.start()
    print("Done.")

    # If the user specifies a FicTrac config file, turn on tracking by start the tracking task
    if (options.fictrac_config is not None):
        tracTask = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                 options.fictrac_callback, options.pgr_enable)

        # Run the task
        sys.stdout.write("Starting FicTrac ... ")
        tracTask.run()
        print("Done")

    sys.stdout.write("Queing playlist ... ")
    time.sleep(1)
    daqTask.send(stimPlaylist)
    time.sleep(1)
    print("Done")

    # Start the playback and aquistion by sending a start signal.
    daqTask.send(["START", options])

    time.sleep(2)

    # Wait till the user presses enter to end playback
    raw_input("Press ENTER to end playback ... ")

    sys.stdout.write("Shutting down ... ")
    daqTask.send("STOP")
    time.sleep(2)
    daqTask.close()
    print("Done")

if __name__ == '__main__':
    freeze_support()
    main()