import time
import configargparse


# A custom action to process command line options that are
# comma separated lists. Splits and trims whitespace.
class CommaListParser(configargparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        x = [x.strip() for x in values.split(',')]
        setattr(args, self.dest, x)


# A custom action to process command line options that are
# comma separated lists of numbers. Splits and trims whitespace, then converts to floats.
class CommaListNumParser(configargparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        x = [float(x.strip()) for x in values.split(',')]
        setattr(args, self.dest, x)


def validatate_args(options):
    if options.ball_control_enable:
        # Make sure the user has passed in the appropriate parameters
        if not options.ball_control_periods:
            raise ValueError("Ball control is enabled but no ball_control_periods parameter has been specified.")

        if not options.ball_control_durations:
            raise ValueError("Ball control is enabled but no ball_control_durations parameter has been specified.")

        if len(options.ball_control_periods) != len(options.ball_control_durations):
            raise ValueError(
                "ball_control_periods and ball_control_durations must have same length, one duration for each period.")


# need to add photosensor argument (and logic)
# need to add in calibration path argument
# need to add in matplotlib plotting command-line argument
def parse_arguments(args=None):
    savefilename = time.strftime('Y%m%d_%H%M_daq.h5')

    # Setup program command line argument parser
    parser = configargparse.ArgumentParser()
    parser.add('-c', '--config', required=True, is_config_file=True, help='Path to a configuration file.')
    parser.add_argument('-v', help='Verbose output', default=False, dest='verbose', action='store_true')
    parser.add_argument("-p", "--stim_playlist", dest="stim_playlist",
                        help="A playlist file of auditory stimuli")
    parser.add_argument("-a", "--attenuation_file", dest="attenuation_file",
                        help="A file specifying the attenuation function")
    parser.add_argument('-i', "--analog_in_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of numbers specifying the input channels record. Default channel is 0.",
                        default=[0])
    parser.add_argument("--digital_in_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of channels specifying the digital input channels record. Default is None.",
                        default=None)
    parser.add_argument('-o', "--analog_out_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of numbers specifying the output channels. Default none for no output")
    parser.add_argument("--addSyncOutput", action="store_true",
                        help="Send a 5V power signal to the last AO channel for visual synchronization.",
                        default=False)
    parser.add_argument("--visual_stimulus",
                        type=str,
                        help="A pre-defined visual stimulus",
                        default='grating')
    parser.add_argument("--screen_calibration",
                        type=str,
                        help="Where to find the (pre-computed) screen calibration file",
                        default='')
    parser.add_argument("--use_RSE",
                        help="Use RSE (as opposed to differential) denoising on AI DAQ inputs",
                        default=True)
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
    parser.add_argument("--fictrac_plot_state", action="store_true",
                        help="Enable plotting of FicTrac state history.",
                        default=False)
    parser.add_argument("--pgr_cam_enable", action="store_true",
                        help="Enable Point Grey Camera support in FicTrac.",
                        default=False)
    parser.add_argument("--shuffle", action="store_true", dest="shuffle",
                        help="Shuffle the playback of the playlist randomly.",
                        default=False)
    parser.add_argument("--start_delay", type=float,
                        help="Delay the start of playback and acquisition from FicTrac tracking by this many seconds. " +
                             "The default is 0 seconds.",
                        default=0.0)
    parser.add_argument("--callback", type=str,
                        help='Filename of Python code that contains implementaion of FlyVRCallback class. Used to plugin' +
                             'custom control logic for closed loop experiments.', default=None)
    parser.add_argument("--ball_control_enable", action="store_true",
                        default=False,
                        help='Enable control signals for stepper motor controlling ball motion. Used for testing of closed loop setup.')
    parser.add_argument("--ball_control_channel", type=str,
                        default='port0/line3:4',
                        help='String with name of two bit digital channels to send ball signal.')
    parser.add_argument("--ball_control_periods",
                        type=str,
                        action=CommaListNumParser,
                        help="A comma separated list of periods (in milliseconds) describing how to construct the ball control signal.")
    parser.add_argument("--ball_control_durations",
                        type=str,
                        action=CommaListNumParser,
                        help="A comma separated list of durations (in seconds) for each period in the ball_control_periods parameter.")
    parser.add_argument("--ball_control_loop", action="store_true",
                        default=True,
                        help='Whether the ball control signal should loop idefinitely or not.')

    # required = "stim_playlist".split()
    required = "".split()

    if args:
        options = parser.parse_args(args)
    else:
        options = parser.parse_args()

    # Check for required arguments
    for r in required:
        if options.__dict__[r] is None:
            parser.print_help()
            parser.error("parameter %s required" % r)

    validatate_args(options)

    return options