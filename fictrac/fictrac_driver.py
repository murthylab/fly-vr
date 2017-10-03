import shmem_transfer_data
import sys
import os
import mmap
import ctypes
import subprocess

from common.tools import which

class FicTracDriver:
    """
    This class drives the tracking of the fly via a separate software called FicTrac. It invokes this process and
    calls a callback function once for each time the tracking state of the insect is updated.
    """
    def __init__(self, config_file, console_ouput_file, track_change_callback, pgr_enable=False):
        """
        Create the FicTrac driver object. This function will perform a check to see if the FicTrac program is present
        on the path. If it is not, it will throw an exception.

        :param str config_file: The path to the configuration file that should be passed to the FicTrac command.
        :param str console_output_file: The path to the file where console output should be stored.
        :param track_change_callback: A callback function which is called once everytime tracking status changes. This
        function should have one argument; an object representing the current tracking state as 15 parameters. These are
        the same parameters that FicTrac records in its ouput log file.
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

    def run(self):
        """
        Start the the FicTrac process and block till it closes. This function will poll a shared memory region for
        changes in tracking data and invoke a callback function when they occur. FicTrac is assumed to exist on the
        system path.

        :return:
        """

        # Open or create the shared memory region for accessing FicTrac's state
        shmem = mmap.mmap(-1, ctypes.sizeof(shmem_transfer_data.SHMEMFicTracState), "FicTracStateSHMEM")

        # Start FicTrac
        with open(self.console_output_file, "wb") as out:
            fictrac_process = subprocess.Popen([self.fictrac_bin_fullpath, self.config_file], stdout=out, stderr=subprocess.STDOUT)

            data = shmem_transfer_data.SHMEMFicTracState.from_buffer(shmem)
            old_frame_count = data.frame_cnt
            print("Waiting for FicTrac updates in shared memory ... ")
            while fictrac_process.poll() is None:
                data = shmem_transfer_data.SHMEMFicTracState.from_buffer(shmem)
                new_frame_count = data.frame_cnt

                if old_frame_count != new_frame_count:
                    old_frame_count = new_frame_count
                    self.track_change_callback(data)

def tracking_update_stub(data):
    shmem_transfer_data.print_fictrac_state(data)

if __name__ == '__main__':
    tracTask = FicTracDriver('tests/test_data/fictrac/config.txt', 'tests/test_data/fictrac/output.txt', tracking_update_stub)
    tracTask.run()