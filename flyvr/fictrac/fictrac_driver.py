import os
import ctypes
import subprocess
import time

import numpy as np

from flyvr.common.tools import which
from flyvr.fictrac.shmem_transfer_data import new_mmap_shmem_buffer, new_mmap_signals_buffer, \
    SHMEMFicTracState, fictrac_state_to_vec, NUM_FICTRAC_FIELDS


def fictrac_poll_run_main(message_pipe, trac_drviver, state):
    trac_drviver.run(message_pipe, state)


class FicTracDriver(object):
    """
    This class drives the tracking of the fly via a separate software called FicTrac. It invokes this process and
    calls a control function once for each time the tracking state of the insect is updated.
    """

    def __init__(self, config_file, console_ouput_file, pgr_enable=False, experiment=None):
        """
        Create the FicTrac driver object. This function will perform a check to see if the FicTrac program is present
        on the path. If it is not, it will throw an exception.

        :param str config_file: The path to the configuration file that should be passed to the FicTrac command.
        :param str console_output_file: The path to the file where console output should be stored.
        :param bool pgr_enable: Is Point Grey camera support needed. This just decides which executable to call, either
        'FicTrac' or 'FicTrac-PGR'.
        """

        self.config_file = config_file
        self.console_output_file = console_ouput_file
        self.pgr_enable = pgr_enable
        self.experiment = experiment

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

        self.fictrac_process = None
        self.fictrac_signals = None

    def run(self, message_pipe, state):
        """
        Start the the FicTrac process and block till it closes. This function will poll a shared memory region for
        changes in tracking data and invoke a control function when they occur. FicTrac is assumed to exist on the
        system path.

        :return:
        """
        self.fictrac_signals = new_mmap_signals_buffer()

        # Setup dataset to log FicTrac data to.
        state.logger.create("/fictrac/output", shape=[2048, NUM_FICTRAC_FIELDS],
                            maxshape=[None, NUM_FICTRAC_FIELDS], dtype=np.float64,
                            chunks=(2048, NUM_FICTRAC_FIELDS))

        # Start FicTrac
        with open(self.console_output_file, "wb") as out:

            self.fictrac_process = subprocess.Popen([self.fictrac_bin_fullpath, self.config_file], stdout=out,
                                                    stderr=subprocess.STDOUT)

            data = new_mmap_shmem_buffer()
            first_frame_count = data.frame_cnt
            old_frame_count = data.frame_cnt
            print("Waiting for FicTrac updates in shared memory ... ")
            while self.fictrac_process.poll() is None:
                new_frame_count = data.frame_cnt

                if old_frame_count != new_frame_count:

                    # If this is our first frame incremented, then send a signal to the
                    # that we have started processing frames
                    if old_frame_count == first_frame_count:
                        state.FICTRAC_READY = 1

                    if new_frame_count - old_frame_count != 1 and state.RUN != 1:
                        self.fictrac_process.terminate()
                        print(("FicTrac frame counter jumped by more than 1! oldFrame = " +
                               str(old_frame_count) + ", newFrame = " + str(new_frame_count)))

                    old_frame_count = new_frame_count

                    # Copy the current state.
                    data_copy = SHMEMFicTracState()
                    ctypes.pointer(data_copy)[0] = data

                    # Log the FicTrac data to our master log file.
                    state.logger.log('/fictrac/output', fictrac_state_to_vec(data_copy))

                # If we detect it is time to shutdown, kill the FicTrac process
                if not state.is_running_well():
                    self.stop()
                    break

        state.FICTRAC_READY = 0

        # Get the fic trac process return code
        if self.fictrac_process.returncode is not None and self.fictrac_process.returncode != 0:
            state.RUN = 0
            state.RUNTIME_ERROR = -5
            raise RuntimeError(
                "FicTrac failed because of an application error. Consult the FicTrac console output file.")

    def stop(self):

        print("Sending stop signal to FicTrac ... ")

        # We keep sending signals to the FicTrac process until it dies
        while self.fictrac_process.poll() is None:
            self.fictrac_signals.send_close()
            time.sleep(0.2)
