import time
import logging
import itertools

import yaml

from flyvr.common.build_arg_parser import parse_arguments, get_printable_options_dict

from flyvr.video.video_server import run_video_server
from flyvr.audio.sound_server import run_sound_server
from flyvr.audio.io_task import run_io
from flyvr.common import SharedState, BACKEND_FICTRAC, BACKEND_DAQ, BACKEND_AUDIO, BACKEND_VIDEO, BACKEND_HWIO
from flyvr.common.inputimeout import inputimeout, TimeoutOccurred
from flyvr.control.experiment import Experiment
from flyvr.common.concurrent_task import ConcurrentTask
from flyvr.fictrac.fictrac_driver import FicTracDriver
from flyvr.fictrac.replay import FicTracDriverReplay
from flyvr.hwio.phidget import run_phidget_io
from flyvr.common.ipc import run_main_relay
from flyvr.gui import run_main_state_gui


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
    # flip the default vs the individual launchers - wait for all of the backends
    options.wait = True

    # save the total state
    _opts = get_printable_options_dict(options, include_experiment_and_playlist=True)
    with open(options.record_file.replace('.h5', '.config.yml'), 'wt') as f:
        yaml.safe_dump(_opts, f)

    log = logging.getLogger('flyvr.main')

    flyvr_shared_state = SharedState(options=options, logger=None, where='main')

    # start the IPC bus first as it is needed by many subsystems
    ipc_bus = ConcurrentTask(task=run_main_relay, comms=None, taskinitargs=[])
    ipc_bus.start()

    # start the GUI
    gui = ConcurrentTask(task=run_main_state_gui, comms=None, taskinitargs=[None, True])
    gui.start()

    backend_wait = [BACKEND_FICTRAC]

    trac_drv = _get_fictrac_driver(options, log)
    if trac_drv is not None:
        fictrac_task = ConcurrentTask(task=trac_drv.run, comms=None, taskinitargs=[options])
        fictrac_task.start()

        # wait till fictrac is processing frames
        flyvr_shared_state.wait_for_backends(BACKEND_FICTRAC)
        log.info('fictrac is ready')

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
        video = None
        log.info('not starting video backend (playlist empty or keepalive_video not specified)')

    if options.keepalive_audio or options.playlist.get('audio'):
        audio = ConcurrentTask(task=run_sound_server, comms=None, taskinitargs=[options])
        backend_wait.append(BACKEND_AUDIO)
        audio.start()
    else:
        audio = None
        log.info('not starting video backend (playlist empty or keepalive_video not specified)')

    log.info('waiting %ss for %r to be ready' % (60, backend_wait))
    if flyvr_shared_state.wait_for_backends(*backend_wait, timeout=60):

        if options.delay < 0:
            log.info('waiting for manual start signal')
            flyvr_shared_state.wait_for_start()
        elif options.delay >= 0:
            if options.delay > 0:
                log.info('delaying startup %ss' % options.delay)
                time.sleep(options.delay)
            log.info('sending start signal')
            flyvr_shared_state.signal_start()

        for i in itertools.count():
            try:
                inputimeout('\n---------------\nPress any key to finish\n---------------\n\n' if i == 0 else '', 1)
                flyvr_shared_state.signal_stop().join(timeout=5)
                break
            except TimeoutOccurred:
                if flyvr_shared_state.is_stopped():
                    # stopped from elsewhere (gui)
                    break

    else:
        log.error('not all required backends became ready - please check logs for '
                  'error messages')
        flyvr_shared_state.signal_stop()

    log.info('stopped')

    for task in (ipc_bus, gui, hwio, daq, video, audio):
        if task is not None:
            log.debug('closing subprocess: %r' % task)
            task.close()

    log.info('finished')
