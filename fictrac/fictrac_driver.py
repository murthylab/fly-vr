import os
import mmap
import ctypes
import subprocess
import time

import numpy as np

from common.tools import which
from common.concurrent_task import ConcurrentTask
from fictrac.shmem_transfer_data import SHMEMFicTracState, SHMEMFicTracSignals, fictrac_state_to_vec, NUM_FICTRAC_FIELDS
from fictrac.plot_task import plot_task_fictrac


def fictrac_poll_run_main(message_pipe, tracDrv, state):
    tracDrv.run(message_pipe, state)


class FicTracDriver(object):
    """
    This class drives the tracking of the fly via a separate software called FicTrac. It invokes this process and
    calls a control function once for each time the tracking state of the insect is updated.
    """

    def __init__(self, config_file, console_ouput_file, track_change_callback=None, pgr_enable=False, plot_on=True):
        """
        Create the FicTrac driver object. This function will perform a check to see if the FicTrac program is present
        on the path. If it is not, it will throw an exception.

        :param str config_file: The path to the configuration file that should be passed to the FicTrac command.
        :param str console_output_file: The path to the file where console output should be stored.
        :param track_change_callback: A FlyVRCallback class which is called once everytime tracking status changes. See
        control.FlyVRCallback for example.
        :param bool pgr_enable: Is Point Grey camera support needed. This just decides which executable to call, either
        'FicTrac' or 'FicTrac-PGR'.
        """

        self.config_file = config_file
        self.console_output_file = console_ouput_file
        self.track_change_callback = track_change_callback
        self.pgr_enable = pgr_enable

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

        self.plot_on = plot_on

    def run(self, message_pipe, state):
        """
        Start the the FicTrac process and block till it closes. This function will poll a shared memory region for
        changes in tracking data and invoke a control function when they occur. FicTrac is assumed to exist on the
        system path.

        :return:
        """

        # Setup anything the callback needs.
        if self.track_change_callback is not None:
            self.track_change_callback.setup_callback()

        # Open or create the shared memory region for accessing FicTrac's state
        shmem = mmap.mmap(-1, ctypes.sizeof(SHMEMFicTracState), "FicTracStateSHMEM")

        # Open or create another shared memory region, this one lets us signal to fic trac to shutdown.
        shmem_signals = mmap.mmap(-1, ctypes.sizeof(ctypes.c_int32), "FicTracStateSHMEM_SIGNALS")

        self.fictrac_signals = SHMEMFicTracSignals.from_buffer(shmem_signals)

        # Setup dataset to log FicTrac data to.
        state.logger.create("/fictrac/output", shape=[2048, NUM_FICTRAC_FIELDS],
                            maxshape=[None, NUM_FICTRAC_FIELDS], dtype=np.float64,
                            chunks=(2048, NUM_FICTRAC_FIELDS))

        # Start FicTrac
        with open(self.console_output_file, "wb") as out:

            self.fictrac_process = subprocess.Popen([self.fictrac_bin_fullpath, self.config_file], stdout=out,
                                                    stderr=subprocess.STDOUT)

            if self.plot_on:
                self.plot_task = ConcurrentTask(task=plot_task_fictrac, comms="pipe",
                                                taskinitargs=[state])
                self.plot_task.start()

            data = SHMEMFicTracState.from_buffer(shmem)
            first_frame_count = data.frame_cnt
            old_frame_count = data.frame_cnt
            print("Waiting for FicTrac updates in shared memory ... ")
            while self.fictrac_process.poll() is None:
                new_frame_count = data.frame_cnt

                if old_frame_count != new_frame_count:

                    # If this is our first frame incremented, then send a signal to the
                    # that we have started processing frames
                    if old_frame_count == first_frame_count:
                        state.FICTRAC_READY.value = 1

                    if new_frame_count - old_frame_count != 1 and state.RUN.value != 1:
                        self.fictrac_process.terminate()
                        print(("FicTrac frame counter jumped by more than 1! oldFrame = " +
                               str(old_frame_count) + ", newFrame = " + str(new_frame_count)))

                    old_frame_count = new_frame_count
                    state.FICTRAC_FRAME_NUM.value = new_frame_count

                    # Copy the current state.
                    data_copy = SHMEMFicTracState()
                    ctypes.pointer(data_copy)[0] = data

                    # Log the FicTrac data to our master log file.
                    state.logger.log('/fictrac/output', fictrac_state_to_vec(data_copy))

                    if self.track_change_callback is not None:
                        self.track_change_callback.process_callback(data_copy)

                # If we detect it is time to shutdown, kill the FicTrac process
                if not state.is_running_well():
                    self.stop()
                    break

        state.FICTRAC_READY.value = 0

        # Call the callback shutdown code.
        if self.track_change_callback is not None:
            self.track_change_callback.shutdown_callback()

        # Get the fic trac process return code
        if self.fictrac_process.returncode is not None and self.fictrac_process.returncode != 0:
            state.RUN.value = 0
            state.RUNTIME_ERROR = -5
            raise RuntimeError(
                "FicTrac failed because of an application error. Consult the FicTrac console output file.")

    def stop(self):

        print("Sending stop signal to FicTrac ... ")

        # We keep sending signals to the FicTrac process until it dies
        while self.fictrac_process.poll() is None:
            self.fictrac_signals.send_close()
            time.sleep(0.2)
