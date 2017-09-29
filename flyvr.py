import time
import sys
from multiprocessing import freeze_support

from optparse import OptionParser

from audio import io_task
from audio.attenuation import Attenuator
from audio.stimuli import SinStim, AudioStimPlaylist

from common.concurrent_task import ConcurrentTask

savefilename = time.strftime('Y%m%d_%H%M_daq.h5')

# A small callback function to process command line options that are
# comma separated lists. Splits and trims whitespace.
def comma_list_callback(option, opt, value, parser):
    x = [x.strip() for x in value.split(',')]
    setattr(parser.values, option.dest, x)

def main():

    # Setup program command line argument parser
    parser = OptionParser(version="%prog 0.1")
    parser.add_option("-p", "--stim_playlist", dest="stim_playlist",
                      help="A playlist file of auditory stimuli")
    parser.add_option("-a", "--attenuation_file", dest="attenuation_file",
                      help="A file specifying the attenuation function")
    parser.add_option('-i', "--analog_in_channels",
                      type="string",
                      action='callback',
                      callback=comma_list_callback,
                      help="A comma separated list of numbers specifying the input channels record. Default channel is 0.",
                      default=[0])
    parser.add_option('-o', "--analog_out_channels",
                      type="string",
                      action='callback',
                      callback=comma_list_callback,
                      help="A comma separated list of numbers specifying the output channels. Default channel is 0.",
                      default=[0])
    parser.add_option('-d', "--display_input_channel",
                      type="string",
                      help="Input channel to display in realtime. Default is channel 0.",
                      default=0)
    parser.add_option('-l', "--record_file",
                      type="string",
                      help="File that stores output recorded on requested input channels. Default is file is Y%m%d_%H%M_daq.h5 where Y%m%d_%H%M is current timestamp.",
                      default=savefilename)
    parser.add_option("-s", action="store_true", dest="shuffle",
                      help="Shuffle the playback of the playlist randomly.",
                      default=False)
    required = "stim_playlist".split()
    (options, args) = parser.parse_args()

    # Check for required arguments
    for r in required:
        if options.__dict__[r] is None:
            parser.print_help()
            parser.error("parameter %s required" % r)

    # Read the playlist file and create and audio stimulus playlist object
    stimPlaylist = AudioStimPlaylist.fromfilename(options.stim_playlist, options.shuffle)

    # If the user passed in an attenuation file function, apply it to the playlist
    if(options.attenuation_file is not None):
        attenuator = Attenuator.load_from_file(options.attenuation_file)
        for stim in stimPlaylist.stims:
            stim.attenuator = attenuator
    else:
        print("Warning: No attenuation file specified.")

    sys.stdout.write("Initializing DAQ Tasks ... ")
    daqTask = ConcurrentTask(task=io_task.io_task_main, comms="pipe", taskinitargs=[])
    daqTask.start()
    print("Done.")

    sys.stdout.write("Queing playlist ... ")
    time.sleep(1)
    daqTask.send(stimPlaylist)
    time.sleep(1)
    print("Done")

    # Start the playback and aquistion by sending a start signal.
    daqTask.send(["START", options, args])

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