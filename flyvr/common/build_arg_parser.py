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
        savefilename = time.strftime('%Y%m%d_%H%M.h5')

    parser = configargparse.ArgumentParser(config_file_parser_class=YamlConfigParser,
                                           ignore_unknown_config_file_keys=True,
                                           args_for_setting_config_path=['-c', '--config'])
    parser.add_argument('-v', '--verbose', help='Verbose output.', default=False, dest='verbose', action='store_true')
    parser.add_argument("--attenuation_file", dest="attenuation_file",
                        help="A file specifying the attenuation function.")
    parser.add_argument("-e", "--experiment_file", action=FixNoneParser,
                        help="A file defining the experiment (can be a python file or a .yaml).")
    parser.add_argument("-p", "--playlist_file", action=FixNoneParser,
                        help="A file defining the playlist, replaces any playlist defined in the main configuration "
                             "file")
    parser.add_argument("--screen_calibration", action=FixNoneParser,
                        help="Where to find the (pre-computed) screen calibration file.")
    parser.add_argument("--use_RSE", action='store_true',
                        help="Use RSE (as opposed to differential) denoising on AI DAQ inputs.",
                        default=True)
    parser.add_argument("--remote_2P_disable", action="store_true",
                        help="Disable remote start, stop, and next file signaling the 2-Photon imaging "
                             "(if the phidget is not detected, signalling is disabled with a warning).",
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
    parser.add_argument("--scanimage_next_start_delay",
                        type=int,
                        help="The delay [ms] between next and start pulses when signaling the 2-photon remote "
                             "(<0 disables sending a start after a next).",
                        default=300)
    parser.add_argument("--remote_2P_next_disable", action="store_true",
                        help="Disable remote next (+start) signaling every stimulus item. "
                             "Just signal start and stop at the beginning and end of an experiment.",
                        default=False)
    parser.add_argument("--phidget_network",
                        action='store_true',
                        help='connect to phidget over network protocol (required for some motor-on-ball CL tests)',
                        default=False)
    parser.add_argument('--keepalive_video', action='store_true',
                        help="Keep the video process running even if they initially provided playlist contains "
                             "no video items (such as if you want to later play dynamic video items not declared "
                             "in the playlist).",
                        default=False)
    parser.add_argument('--keepalive_audio', action='store_true',
                        help="Keep the audio process running even if they initially provided playlist contains "
                             "no audio items (such as if you want to later play dynamic audio items not declared "
                             "in the playlist).",
                        default=False)
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
                        help="Disable Point Grey Camera support in FicTrac.",
                        default=False)
    parser.add_argument("--wait", action="store_true",
                        help="Wait for start signal before proceeding (default false in single process backends,  "
                             "and always true in the main launcher).",
                        default=False)
    parser.add_argument("--delay", type=int, default=5,
                        help="Delay main startup by this many seconds. Negative number means wait forever.")
    parser.add_argument('--projector_disable', action='store_true', help='Do not setup projector in video backend.')
    parser.add_argument('--samplerate_daq', default=10000, type=int,
                        help='DAQ sample rate (advanced option, do not change)')
    parser.add_argument('--print-defaults', help='Print default config values', action='store_true')

    return parser


_EXP_SUB_NAMESPACES = ('state', 'time')


def _get_experiment_namespace(conf):
    return conf.get('experiment', conf)


def setup_experiment(options):
    from flyvr.control.experiment import Experiment

    if options.config_file:
        with open(options.config_file) as f:
            _all_conf = yaml.safe_load(f)
    else:
        _all_conf = {}

    _experiment_obj = None
    _experiment = {}

    def _build_experiment_inline(_conf):
        __experiment = {}
        for _exp_what in _EXP_SUB_NAMESPACES:
            try:
                __experiment[_exp_what] = _conf[_exp_what]
            except KeyError:
                pass

        if __experiment:
            return Experiment.from_items(state_item_defns=__experiment.get('state') or {},
                                         timed_item_defns=__experiment.get('time') or {})

    _experiment_yaml = None
    if options.experiment_file:

        _, ext = os.path.splitext(options.experiment_file)
        if ext == '.py':
            _experiment_obj = Experiment.new_from_python_file(options.experiment_file)
        elif ext in ('.yaml', '.yml'):
            with open(options.experiment_file) as f:
                dat = yaml.safe_load(f)
            _experiment_obj = _build_experiment_inline(_get_experiment_namespace(dat))

            if _experiment_obj is not None:
                _experiment_yaml = dat

    else:
        _experiment_obj = _build_experiment_inline(_get_experiment_namespace(_all_conf))

    options.experiment = _experiment_obj

    if options.experiment:
        # noinspection PyProtectedMember
        options.experiment._set_playlist(options.playlist)


def get_printable_options_dict(options, include_experiment_and_playlist=False):

    # need to keep the raw config around for the inline yaml experiment path
    if options.config_file:
        with open(options.config_file) as f:
            _all_conf = yaml.safe_load(f)
    else:
        _all_conf = {}

    _opts = dict(vars(options))
    _opts.pop('record_file', None)
    _opts.pop('config_file', None)

    _opts.pop('experiment', None)  # not representable as is, it's an object
    if options.verbose or include_experiment_and_playlist:
        if options.experiment_file:
            _, ext = os.path.splitext(options.experiment_file)
            if ext in ('.yaml', '.yml'):
                with open(options.experiment_file) as f:
                    _opts['experiment'] = yaml.safe_load(f)
        else:
            _exp = _get_experiment_namespace(_all_conf)
            if _exp:
                _opts['experiment'] = {k: _exp[k] for k in _EXP_SUB_NAMESPACES if k in _exp}

    else:
        _opts.pop('playlist', None)

    return _opts


def parse_options(options, parser):
    required = "".split()

    # Check for required arguments
    for r in required:
        if options.__dict__[r] is None:
            parser.print_help()
            parser.error("parameter %s required" % r)

    _config_file_path = None

    if options.config_file:
        with open(options.config_file) as f:
            _all_conf = yaml.safe_load(f)
            _config_file_path = os.path.abspath(options.config_file)
    else:
        _all_conf = {}

    options.analog_in_channels = dict(_all_conf.get('configuration', {}).get('analog_in_channels') or {})
    options.analog_out_channels = dict(_all_conf.get('configuration', {}).get('analog_out_channels') or {})

    if len(options.analog_out_channels) > 1:
        raise NotImplementedError('only a single DAQ output channel is supported')

    try:
        _playlist = _all_conf['playlist']
    except KeyError:
        _playlist = {}

    if options.playlist_file:
        from flyvr.common import BACKEND_DAQ, BACKEND_AUDIO, BACKEND_VIDEO

        # noinspection PyBroadException
        try:
            _used_extra_playlist = False

            with open(options.playlist_file) as f:
                _extra_playlist_conf = yaml.safe_load(f)

            if 'playlist' in _extra_playlist_conf:
                _playlist = _extra_playlist_conf['playlist']
                _used_extra_playlist = True
            elif any(be in _extra_playlist_conf for be in (BACKEND_DAQ, BACKEND_AUDIO, BACKEND_VIDEO)):
                _playlist = _extra_playlist_conf
                _used_extra_playlist = True

            if _used_extra_playlist:
                _config_file_path = os.path.abspath(options.playlist_file)

        except Exception:
            pass

    options.playlist = _playlist
    options.experiment = None

    if options.print_defaults:
        _opts = get_printable_options_dict(options)
        print(yaml.safe_dump(_opts), end='')
        parser.exit(0)

    options._config_file_path = _config_file_path

    return options


def setup_logging(options):
    logging.basicConfig(level=logging.DEBUG if options.verbose else logging.INFO,
                        format='%(name)-40s: %(levelname)-8s %(message)s')
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
