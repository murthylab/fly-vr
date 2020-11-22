import logging

from flyvr.common.build_arg_parser import parse_arguments

from flyvr.video.video_server import run_video_server
from flyvr.audio.sound_server import run_sound_server
from flyvr.audio.io_task import run_io
from flyvr.common import SharedState, BACKEND_FICTRAC, BACKEND_DAQ, BACKEND_AUDIO, BACKEND_VIDEO, BACKEND_HWIO
from flyvr.control.experiment import Experiment
from flyvr.common.concurrent_task import ConcurrentTask
from flyvr.common.logger import DatasetLogServer
from flyvr.fictrac.fictrac_driver import FicTracDriver
from flyvr.fictrac.replay import FicTracDriverReplay
from flyvr.hwio.phidget import run_phidget_io
from flyvr.common.ipc import run_main_relay


def _get_fictrac_driver(options, log):
    drv = None

    if options.fictrac_config is not None:
        experiment = None
        if options.experiment:
            assert isinstance(options.experiment, Experiment)
            experiment = options.experiment

            log.info('initialized experiment %r' % experiment)

        if options.fictrac_config.endswith('.h5'):
            drv = FicTracDriverReplay(options.fictrac_config)

            log.info('starting fictrac replay of %s' % options.fictrac_config)
        else:
            if not options.fictrac_console_out:
                log.fatal('fictrac console out must be provided for fictrac performance')
                return None

            drv = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                experiment=experiment,
                                pgr_enable=not options.pgr_cam_disable)

            log.info('starting fictrac%s driver with config %s' % (
                '' if options.pgr_cam_disable else ' PGR',
                options.fictrac_config)
            )

    else:
        log.fatal('fictrac config not provided')

    return drv


def main_fictrac():
    log = logging.getLogger('flyvr.main_fictrac')

    options, parser = parse_arguments(return_parser=True)

    trac_drv = _get_fictrac_driver(options, log)
    if trac_drv is None:
        raise parser.error('fictrac configuration error')

    trac_drv.run(options)


def main_launcher():
    options = parse_arguments()

    # flip the default vs the individual launchers - we do need to wait for
    # all of the backends
    options.wait = True

    log = logging.getLogger('flyvr.main')

    # start the IPC bus first as it is needed by many subsystems
    ipc_bus = ConcurrentTask(task=run_main_relay, comms=None, taskinitargs=[])
    ipc_bus.start()

    log_server = DatasetLogServer()
    logger = log_server.start_logging_server(options.record_file)

    flyvr_shared_state = SharedState(options=options, logger=logger, where='main')

    backend_wait = [BACKEND_FICTRAC]

    trac_drv = _get_fictrac_driver(options, log)
    if trac_drv is not None:
        fictrac_task = ConcurrentTask(task=trac_drv.run, comms="pipe",
                                      taskinitargs=[options])
        fictrac_task.start()

        # wait till fictrac is processing frames
        flyvr_shared_state.wait_for_backends(BACKEND_FICTRAC)

    # start the other mainloops

    # these always run
    hwio = ConcurrentTask(task=run_phidget_io, comms=None, taskinitargs=[options])
    backend_wait.append(BACKEND_HWIO)
    hwio.start()

    daq = ConcurrentTask(task=run_io, comms=None, taskinitargs=[options])
    backend_wait.append(BACKEND_DAQ)
    daq.start()

    # these are optional
    if options.keepalive_video or options.playlist.get('video'):
        video = ConcurrentTask(task=run_video_server, comms=None, taskinitargs=[options])
        backend_wait.append(BACKEND_VIDEO)
        video.start()
    else:
        log.info('not starting video backend (playlist empty or keepalive_video not specified)')

    if options.keepalive_audio or options.playlist.get('audio'):
        audio = ConcurrentTask(task=run_sound_server, comms=None, taskinitargs=[options])
        backend_wait.append(BACKEND_AUDIO)
        audio.start()
    else:
        log.info('not starting video backend (playlist empty or keepalive_video not specified)')

    log.info('waiting for %r to be ready' % (backend_wait, ))
    flyvr_shared_state.wait_for_backends(*backend_wait)

    # fixme: dont always start? move start to UI?
    flyvr_shared_state.signal_start()

    while True:
        input('Press any key to finish')
        flyvr_shared_state.signal_stop().join(timeout=5)
        break

