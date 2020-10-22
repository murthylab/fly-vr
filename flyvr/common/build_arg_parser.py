import time
import logging
import os.path

import yaml
import configargparse


# A custom action to process command line options that are
# comma separated lists. Splits and trims whitespace.
class CommaListParser(configargparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        if (values is not None) and (values != 'None'):
            try:
                x = [x.strip() for x in values.split(',')]
                setattr(args, self.dest, x)
            except Exception as e:
                raise Exception('parameter: %s (%s)' % (self.dest, e))


# A custom action to process command line options that are
# comma separated lists of numbers. Splits and trims whitespace, then converts to floats.
class CommaListNumParser(configargparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        if (values is not None) and (values != 'None'):
            try:
                x = [float(x.strip()) for x in values.split(',')]
                setattr(args, self.dest, x)
            except Exception as e:
                raise Exception('parameter: %s (%s)' % (self.dest, e))


class FixNoneParser(configargparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        if values is not None:
            if values == 'None':
                setattr(args, self.dest, None)
            else:
                setattr(args, self.dest, values)


class YamlConfigParser(configargparse.YAMLConfigFileParser):

    def parse(self, stream):
        try:
            parsed_obj = yaml.safe_load(stream)
        except Exception as e:
            raise configargparse.ConfigFileParserException("Couldn't parse config file: %s" % e)

        config = parsed_obj.get('configuration', {})

        return super().parse(yaml.safe_dump(config))


def build_argparser(savefilename=None):
    if savefilename is None:
        savefilename = time.strftime('Y%m%d_%H%M_daq.h5')

    parser = configargparse.ArgumentParser(config_file_parser_class=YamlConfigParser,
                                           args_for_setting_config_path=['-c', '--config'])
    parser.add_argument('-v', help='Verbose output', default=False, dest='verbose', action='store_true')
    parser.add_argument("--attenuation_file", dest="attenuation_file",
                        help="A file specifying the attenuation function")
    parser.add_argument("-e", "--experiment_file", dest="experiment_file", action=FixNoneParser,
                        help="A file defining the experiment (can be a python file or a .yaml)")
    parser.add_argument("--analog_in_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of numbers specifying the input channels record."
                             "Default channel is 0.",
                        default=[0])
    parser.add_argument("--digital_in_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of channels specifying the digital input channels record."
                             "Default is None.",
                        default=None)
    parser.add_argument("--analog_out_channels",
                        type=str,
                        action=CommaListParser,
                        help="A comma separated list of numbers specifying the output channels."
                             "Default none for no output")
    parser.add_argument("--screen_calibration", action=FixNoneParser,
                        help="Where to find the (pre-computed) screen calibration file")
    parser.add_argument("--use_RSE", action='store_true',
                        help="Use RSE (as opposed to differential) denoising on AI DAQ inputs",
                        default=True)
    parser.add_argument("--remote_2P_enable", action="store_true",
                        help="Enable remote start, stop, and next file signaling the 2-Photon imaging.",
                        default=False)
    parser.add_argument("--remote_start_2P_channel",
                        type=int,
                        help="The digital channel to send remote start signal for 2-photon imaging.",
                        default=3)
    parser.add_argument("--remote_stop_2P_channel",
                        type=int,
                        help="The digital channel to send remote stop signal for 2-photon imaging.",
                        default=4)
    parser.add_argument("--remote_next_2P_channel",
                        type=int,
                        help="The digital channel to send remote next file signal for 2-photon imaging.",
                        default=5)
    parser.add_argument('-l', "--record_file",
                        type=str,
                        help="File that stores output recorded on requested input channels. "
                             "Default is file is Ymd_HM_daq.h5 where Ymd_HM is current timestamp.",
                        default=savefilename)
    parser.add_argument('-f', "--fictrac_config", action=FixNoneParser,
                        help="File that specifies FicTrac configuration information.")
    parser.add_argument('-m', "--fictrac_console_out", action=FixNoneParser,
                        help="File to save FicTrac console output to.")
    parser.add_argument("--pgr_cam_disable", action="store_true",
                        help="Dnable Point Grey Camera support in FicTrac.",
                        default=False)
    parser.add_argument("--start_delay", type=float,
                        help="Delay the start of playback and acquisition from FicTrac tracking by this many seconds. "
                             "The default is 0 seconds.",
                        default=0.0)

    return parser


def parse_options(options, parser):
    from flyvr.control.experiment import Experiment

    required = "".split()

    # Check for required arguments
    for r in required:
        if options.__dict__[r] is None:
            parser.print_help()
            parser.error("parameter %s required" % r)

    if options.config_file:
        with open(options.config_file) as f:
            _all_conf = yaml.safe_load(f)
    else:
        _all_conf = {}

    try:
        _playlist = _all_conf['playlist']
    except KeyError:
        _playlist = {}

    _experiment_obj = None
    _experiment = {}

    def _build_experiment_inline(_conf):
        __experiment = {}
        for _exp_what in ('state', 'time'):
            try:
                __experiment[_exp_what] = _conf[_exp_what]
            except KeyError:
                pass

        if __experiment:
            return Experiment.from_items(state_item_defns=__experiment.get('state') or {},
                                         timed_item_defns=__experiment.get('time') or {})

    if options.experiment_file:

        _, ext = os.path.splitext(options.experiment_file)
        if ext == '.py':
            _experiment_obj = Experiment.new_from_python_file(options.experiment_file)
        elif ext in ('.yaml', '.yml'):
            with open(options.experiment_file) as f:
                dat = yaml.safe_load(f)
            _experiment_obj = _build_experiment_inline(dat)

    else:
        _experiment_obj = _build_experiment_inline(_all_conf)

    options.playlist = _playlist
    options.experiment = _experiment_obj

    return options


def setup_logging(options):
    logging.basicConfig(level=logging.DEBUG if options.verbose else logging.INFO,
                        format='%(name)-35s: %(levelname)-8s %(message)s')
    logging.getLogger('PIL.Image').setLevel(logging.INFO)
    logging.getLogger('PIL.PngImagePlugin').setLevel(logging.INFO)


def parse_arguments(args=None, return_parser=False):
    parser = build_argparser()

    if args:
        options = parser.parse_args(args)
    else:
        options = parser.parse_args()

    options = parse_options(options, parser)

    setup_logging(options)

    if return_parser:
        return options, parser
    else:
        return options
