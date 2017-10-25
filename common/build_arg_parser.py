import time
import configargparse

# A custom action to process command line options that are
# comma separated lists. Splits and trims whitespace.
class CommaListParser(configargparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        x = [x.strip() for x in values.split(',')]
        setattr(args, self.dest, x)

def parse_arguments():
    savefilename = time.strftime('Y%m%d_%H%M_daq.h5')

    # Setup program command line argument parser
    parser = configargparse.ArgumentParser(version="%prog 0.1")
    parser.add('-c', '--config', required=True, is_config_file=True, help='Path to a configuration file.')
    parser.add_argument("-p", "--stim_playlist", dest="stim_playlist",
                        help="A playlist file of auditory stimuli")
    parser.add_argument("-a", "--attenuation_file", dest="attenuation_file",
                        help="A file specifying the attenuation function")
    parser.add_argument('-i', "--analog_in_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of numbers specifying the input channels record. Default channel is 0.",
                        default=[0])
    parser.add_argument('-o', "--analog_out_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of numbers specifying the output channels. Default channel is 0.",
                        default=[0])
    parser.add_argument("--remote_2P_enable", action="store_true",
                        help="Enable remote start, stop, and next file signaling the 2-Photon imaging.",
                        default=False)
    parser.add_argument("--remote_start_2P_channel",
                        type=str,
                        help="The digital channel to send remote start signal for 2-photon imaging. Default = port0/line0",
                        default="port0/line0")
    parser.add_argument("--remote_stop_2P_channel",
                        type=str,
                        help="The digital channel to send remote stop signal for 2-photon imaging. Default = port0/line1.",
                        default="port0/line1")
    parser.add_argument("--remote_next_2P_channel",
                        type=str,
                        help="The digital channel to send remote next file signal for 2-photon imaging. Default = port0/line2.",
                        default="port0/line2")
    parser.add_argument('-l', "--record_file",
                        type=str,
                        help="File that stores output recorded on requested input channels. Default is file is Ymd_HM_daq.h5 where Ymd_HM is current timestamp.",
                        default=savefilename)
    parser.add_argument('-f', "--fictrac_config",
                        type=str,
                        help="File that specifies FicTrac configuration information.")
    parser.add_argument('-m', "--fictrac_console_out",
                        type=str,
                        help="File to save FicTrac console output to.")
    parser.add_argument('-k', "--fictrac_callback",
                        type=str,
                        help="A callback function that will be called anytime FicTrac updates its state. It must take " +
                             "two parameters; the FicTrac state, and an IOTask object for communicating with the daq.")
    parser.add_argument("-g", "--pgr_cam_enable", action="store_true",
                        help="Enable Point Grey Camera support in FicTrac.",
                        default=False)
    parser.add_argument("-s", action="store_true", dest="shuffle",
                        help="Shuffle the playback of the playlist randomly.",
                        default=False)
    required = "stim_playlist".split()
    options = parser.parse_args()

    # Check for required arguments
    for r in required:
        if options.__dict__[r] is None:
            parser.print_help()
            parser.error("parameter %s required" % r)

    return options
