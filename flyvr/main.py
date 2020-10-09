import sys
import time
import logging

from flyvr.common.build_arg_parser import parse_arguments

from flyvr.video.video_server import run_video_server
from flyvr.audio.sound_server import run_sound_server
from flyvr.audio.io_task import run_io
from flyvr.common import SharedState, Every
from flyvr.control.experiment import Experiment
from flyvr.common.concurrent_task import ConcurrentTaskThreaded, ConcurrentTask
from flyvr.common.logger import DatasetLogger, DatasetLogServer
from flyvr.fictrac.fictrac_driver import FicTracDriver, fictrac_poll_run_main
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

    log_server = DatasetLogServer()
    logger = log_server.start_logging_server(options.record_file)

    state = SharedState(options=options, logger=logger)

    trac_drv = _get_fictrac_driver(options, log)
    if trac_drv is None:
        raise parser.error('fictrac configuration error')

    trac_drv.run(None, state)


def main_launcher():
    options = parse_arguments()

    log = logging.getLogger('flyvr.main')

    # start the IPC bus first as it is needed by many subsystems
    ipc_bus = ConcurrentTask(task=run_main_relay, comms=None, taskinitargs=[])
    ipc_bus.start()

    log_server = DatasetLogServer()
    logger = log_server.start_logging_server(options.record_file)

    state = SharedState(options=options, logger=logger)

    trac_drv = _get_fictrac_driver(options, log)

    if trac_drv is not None:
        fictrac_task = ConcurrentTask(task=trac_drv.run, comms="pipe",
                                      taskinitargs=[None, state])
        fictrac_task.start()

        # Wait till FicTrac is processing frames
        while state.FICTRAC_READY == 0 and state.is_running_well():
            time.sleep(0.2)

    # start the other mainloops
    hwio = ConcurrentTask(task=run_phidget_io, comms=None, taskinitargs=[options])
    hwio.start()
    daq = ConcurrentTask(task=run_io, comms=None, taskinitargs=[options])
    daq.start()
    video = ConcurrentTask(task=run_video_server, comms=None, taskinitargs=[options])
    video.start()
    audio = ConcurrentTask(task=run_sound_server, comms=None, taskinitargs=[options])
    audio.start()

    if state.is_running_well():

        log.info("delaying start by %s" % options.start_delay)
        time.sleep(options.start_delay)

        # send a signal to the DAQ to start playback and acquisition
        log.info("signalling DAQ start")
        state.START_DAQ = 1

        # wait until we get a ready message from the DAQ task
        every_3s = Every(15)
        while state.DAQ_READY == 0 and state.is_running_well():
            time.sleep(0.2)
            if every_3s:
                log.info('waiting for DAQ task to signal READY')

        log.info('detected DAQ READY signal')

        # wait till the user presses enter to end session
        if state.is_running_well():
            input("Press ENTER to end session ... ")

