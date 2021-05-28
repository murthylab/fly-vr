import os
import ctypes
import subprocess
import time
import logging

import numpy as np

from flyvr.common import SharedState, BACKEND_FICTRAC
from flyvr.common.build_arg_parser import setup_logging, setup_experiment
from flyvr.common.logger import DatasetLogServer
from flyvr.common.tools import which
from flyvr.fictrac.shmem_transfer_data import new_mmap_shmem_buffer, new_mmap_signals_buffer, \
    SHMEMFicTracState, fictrac_state_to_vec, NUM_FICTRAC_FIELDS


class FicTracDriver(object):
    """
    This class drives the tracking of the fly via a separate software called FicTrac. It invokes this process and
    calls a control function once for each time the tracking state of the insect is updated.
    """

    def __init__(self, config_file, console_ouput_file, pgr_enable=False):
        """
        Create the FicTrac driver object. This function will perform a check to see if the FicTrac program is present
        on the path. If it is not, it will throw an exception.

        :param str config_file: The path to the configuration file that should be passed to the FicTrac command.
        :param str console_ouput_file: The path to the file where console output should be stored.
        :param bool pgr_enable: Is Point Grey camera support needed. This just decides which executable to call, either
        'FicTrac' or 'FicTrac-PGR'.
        """
        self._log = logging.getLogger('flyvr.fictrac.FicTracDriver')

        self.config_file = config_file
        self.console_output_file = console_ouput_file
        self.pgr_enable = pgr_enable
        self.experiment = None

        self.fictrac_bin = 'FicTrac'
        if self.pgr_enable:
            self.fictrac_bin = 'FicTrac-PGR'

        # If this is Windows, we need to add the .exe extension.
        if os.name == 'nt':
            self.fictrac_bin = self.fictrac_bin + ".exe"

        # Lets make sure FicTrac exists on the path
        self.fictrac_bin_fullpath = which(self.fictrac_bin)

        if self.fictrac_bin_fullpath is None:
            raise RuntimeError("Could not find " + self.fictrac_bin + " on the PATH!")

        self._log.debug('fictrac binary: %s' % self.fictrac_bin_fullpath)

        self.fictrac_process = None
        self.fictrac_signals = None

    # noinspection PyUnusedLocal
    def run(self, options=None):
        """
        Start the the FicTrac process and block till it closes. This function will poll a shared memory region for
        changes in tracking data and invoke a control function when they occur. FicTrac is assumed to exist on the
        system path.

        Args:
            options: options loaded from FlyVR config file. If None, driver runs without logging enabled, this is useful
                for testing.

        :return:
        """

        if options is not None:
            setup_logging(options)

            setup_experiment(options)
            if options.experiment:
                self._log.info('initialized experiment %r' % options.experiment)
            self.experiment = options.experiment

            # fixme: this should be threaded and context manager to close
            log_server = DatasetLogServer()

            flyvr_shared_state = SharedState(options=options,
                                             logger=log_server.start_logging_server(options.record_file),
                                             where=BACKEND_FICTRAC)
            if self.experiment:
                # noinspection PyProtectedMember
                self.experiment._set_shared_state(flyvr_shared_state)

            # Setup dataset to log FicTrac data to.
            flyvr_shared_state.logger.create("/fictrac/output", shape=[2048, NUM_FICTRAC_FIELDS],
                                             maxshape=[None, NUM_FICTRAC_FIELDS], dtype=np.float64,
                                             chunks=(2048, NUM_FICTRAC_FIELDS))
        else:
            flyvr_shared_state = None

        self.fictrac_signals = new_mmap_signals_buffer()

        # Start FicTrac
        with open(self.console_output_file, "wb") as out:

            self.fictrac_process = subprocess.Popen([self.fictrac_bin_fullpath, self.config_file], stdout=out,
                                                    stderr=subprocess.STDOUT)

            data = new_mmap_shmem_buffer()
            first_frame_count = data.frame_cnt
            old_frame_count = data.frame_cnt

            running = True
            self._log.info("waiting for fictrac updates in shared memory")
            while (self.fictrac_process.poll() is None) and running:

                # Copy the current fictrac state.
                data_copy = SHMEMFicTracState()
                ctypes.pointer(data_copy)[0] = data

                new_frame_count = data_copy.frame_cnt

                if old_frame_count != new_frame_count:
                    # If this is our first frame incremented, then send a signal to the
                    # that we have started processing frames
                    if old_frame_count == first_frame_count:
                        if flyvr_shared_state:
                            _ = flyvr_shared_state.signal_ready(BACKEND_FICTRAC)

                    if new_frame_count - old_frame_count != 1:
                        # self.fictrac_process.terminate()
                        self._log.error("frame counter jumped by more than 1 (%s vs %s)" % (
                            old_frame_count, new_frame_count))

                    old_frame_count = new_frame_count

                    # Log the FicTrac data to our master log file.
                    if flyvr_shared_state:
                        flyvr_shared_state.logger.log('/fictrac/output', fictrac_state_to_vec(data_copy))

                    if self.experiment is not None:
                        self.experiment.process_state(data_copy)

                # If we detect it is time to shutdown, kill the FicTrac process
                if flyvr_shared_state and flyvr_shared_state.is_stopped():
                    running = False

        self.stop()  # blocks

        self._log.info('fictrac process finished')

        # Get the fictrac process return code
        if self.fictrac_process.returncode is not None and self.fictrac_process.returncode != 0:
            self._log.error('fictrac failed because of an application error. Consult the fictrac console output file')

            if flyvr_shared_state:
                flyvr_shared_state.runtime_error(2)


    def stop(self):
        self._log.info("sending stop signal to fictrac")

        # We keep sending signals to the FicTrac process until it dies
        while self.fictrac_process.poll() is None:
            self.fictrac_signals.send_close()
            time.sleep(0.2)


    def stub(self, logged_data, dat_file_data):
        a = 1