from common.concurrent_task import ConcurrentTask
from . import shmem_transfer_data
from fictrac.shmem_transfer_data import SHMEMFicTracState, fictrac_state_to_vec, NUM_FICTRAC_FIELDS

import os
import mmap
import ctypes
import subprocess
import matplotlib.pyplot as plt
import warnings
import matplotlib.cbook
import numpy as np
import time
from collections import deque

from common.tools import which

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
        self.track_change_callback.setup_callback()

        # Open or create the shared memory region for accessing FicTrac's state
        shmem = mmap.mmap(-1, ctypes.sizeof(shmem_transfer_data.SHMEMFicTracState), "FicTracStateSHMEM")

        # Open or create another shared memory region, this one lets us signal to fic trac to shutdown.
        shmem_signals = mmap.mmap(-1, ctypes.sizeof(ctypes.c_int32), "FicTracStateSHMEM_SIGNALS")

        self.fictrac_signals = shmem_transfer_data.SHMEMFicTracSignals.from_buffer(shmem_signals)

        # Setup dataset to log FicTrac data to.
        state.logger.create("/fictrac/output", shape=[2048, NUM_FICTRAC_FIELDS],
                                              maxshape=[None, NUM_FICTRAC_FIELDS], dtype=np.float64,
                                              chunks=(2048, NUM_FICTRAC_FIELDS))

        # Start FicTrac
        with open(self.console_output_file, "wb") as out:

            self.fictrac_process = subprocess.Popen([self.fictrac_bin_fullpath, self.config_file], stdout=out, stderr=subprocess.STDOUT)

            if self.plot_on:
                self.plot_task = ConcurrentTask(task=plot_task_fictrac, comms="pipe",
                                       taskinitargs=[state])
                self.plot_task.start()

            data = shmem_transfer_data.SHMEMFicTracState.from_buffer(shmem)
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

                    self.track_change_callback.process_callback(data_copy)

                # If we detect it is time to shutdown, kill the FicTrac process
                if not state.is_running_well():
                    self.stop()
                    break

            # Get the fic trac process return code
            # if self.fictrac_process.returncode < 0:
            #     state.RUN.value = 0
            #     state.RUNTIME_ERROR = -1
            #     self.track_change_callback.shutdown_callback()
            #     raise RuntimeError("Fictrac could not start because of an application error. Consult the FicTrac console ouput file.")

        state.FICTRAC_READY.value = 0

        # Call the callback shutdown code.
        self.track_change_callback.shutdown_callback()

    def stop(self):

        print ("Sending stop signal to FicTrac ... ")

        # We keep sending signals to the FicTrac process until it dies
        while self.fictrac_process.poll() is None:
            self.fictrac_signals.send_close()
            time.sleep(0.2)


def angle_diff(angle1, angle2):
    diff = angle2 - angle1
    while diff < np.deg2rad(-180.0):
        diff += np.deg2rad(360.0)
    while diff > np.deg2rad(180):
        diff -= np.deg2rad(360.0)
    return diff

def plot_task_fictrac(disp_queue, flyvr_state,
                      fictrac_state_fields=['speed', 'direction', 'del_rot_cam_vec', 'del_rot_error'],
                      num_history=200):
    """
    A coroutine for plotting fast, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4. This is used
    for plotting streaming data coming from FicTrac.

    :param disp_queue: The message queue from which data is sent for plotting.
    :return: None
    """

    # Open or create the shared memory region for accessing FicTrac's state
    shmem = mmap.mmap(-1, ctypes.sizeof(shmem_transfer_data.SHMEMFicTracState), "FicTracStateSHMEM")

    warnings.filterwarnings("ignore", category=matplotlib.cbook.mplDeprecation)
    plt.ion()

    fig = plt.figure()
    fig.canvas.set_window_title('traces: fictrac')

    # Number of fields to display
    num_channels = len(fictrac_state_fields)

    # Axes limits for each field
    field_ax_limits = {'speed': (0, .03),
                       'direction': (0, 2*np.pi),
                       'heading': (0, 2*np.pi),
                       'heading_diff': (0, 0.261799),
                       'del_rot_error': (0, 15000),
                       'del_rot_cam_vec': (-0.025, 0.025)}

    # Setup a queue for caching the historical data received so we can plot history of samples up to
    # some N
    data_history = deque([SHMEMFicTracState() for i in range(num_history)], maxlen=num_history)

    plot_data = np.zeros((num_history, num_channels))

    # We want to create a subplot for each channel
    axes = []
    backgrounds = []
    point_sets = []
    for chn in range(1, num_channels + 1):
        field_name = fictrac_state_fields[chn-1]
        ax = fig.add_subplot(num_channels, 1, chn)
        ax.set_title(field_name)
        backgrounds.append(fig.canvas.copy_from_bbox(ax.bbox))  # cache the background
        ax.axis([0, num_history, field_ax_limits[field_name][0], field_ax_limits[field_name][1]])
        axes.append(ax)
        point_sets.append(ax.plot(np.arange(num_history), plot_data)[0])  # init plot content

    plt.show()
    plt.draw()
    fig.canvas.start_event_loop(0.001)  # otherwise plot freezes after 3-4 iterations

    RUN = True
    data = shmem_transfer_data.SHMEMFicTracState.from_buffer(shmem)
    first_frame_count = data.frame_cnt
    old_frame_count = data.frame_cnt
    while flyvr_state.is_running_well():
        new_frame_count = data.frame_cnt

        if old_frame_count != new_frame_count:

            # Copy the current state.
            data_copy = SHMEMFicTracState()
            ctypes.pointer(data_copy)[0] = data

            # Append to the history
            data_history.append(data_copy)

            # Turned the queued chunks into a flat array
            sample_i = 0
            last_d = data_history[0]
            for d in data_history:
                chan_i = 0
                for field in fictrac_state_fields:
                    if field.endswith('_diff'):
                        real_field = field.replace('_diff', '')

                        if real_field in ['heading', 'direction']:
                            plot_data[sample_i, chan_i] = abs(angle_diff(getattr(d, real_field), getattr(last_d, real_field)))
                        else:
                            plot_data[sample_i, chan_i] = getattr(d, real_field) - getattr(last_d, real_field)
                    elif field.endswith('vec'):
                        plot_data[sample_i, chan_i] = getattr(d, field)[1]
                    else:
                        plot_data[sample_i,chan_i] = getattr(d, field)
                    chan_i = chan_i + 1
                last_d = d
                sample_i = sample_i + 1

            for chn in range(num_channels):
                fig.canvas.restore_region(backgrounds[chn])         # restore background
                point_sets[chn].set_data(np.arange(num_history), plot_data[:,chn])
                axes[chn].draw_artist(point_sets[chn])              # redraw just the points
                #fig.canvas.blit(axes[chn].bbox)                    # fill in the axes rectangle

            fig.canvas.draw()
            fig.canvas.flush_events()

    # clean up
    plt.close(fig)

def test_fictrac():
    pass

if __name__ == "__main__":
    test_fictrac()