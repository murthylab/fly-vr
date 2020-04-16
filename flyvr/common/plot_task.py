import time
import warnings
from collections import deque

import matplotlib.pyplot as plt
import matplotlib.cbook
import numpy as np

from flyvr.common.concurrent_task import ConcurrentTask
from flyvr.fictrac.shmem_transfer_data import SHMEMFicTracState


def plot_task_daq(disp_queue, channel_names, chunk_size, limit, num_chunks_history=10):
    """
    A coroutine for plotting fast, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4. This is used
    for plotting streaming data recorded as input from the DAQ.

    :param disp_queue: The message queue from which data is sent for plotting.
    :param channel_names: A list of str names for each channel of data.
    :param chunk_size: How many samples will each chunk of data have.
    :param limit: The Y-axis limit of the plot.
    :param num_chunks_history: The number of chunks to keep in the plot history.
    :return: None
    """

    num_channels = len(channel_names)

    # Setup a queue for caching the historical data received so we can plot history of samples up to
    # some N
    data_history = deque([np.zeros((chunk_size, num_channels)) for i in range(num_chunks_history)],
                         maxlen=num_chunks_history)

    warnings.filterwarnings("ignore", category=matplotlib.cbook.mplDeprecation)
    plt.ion()

    fig = plt.figure()
    fig.canvas.set_window_title('traces: daq')

    plot_data = np.zeros((num_chunks_history * chunk_size, num_channels))

    # We want to create a subplot for each channel
    axes = []
    backgrounds = []
    point_sets = []
    for chn in range(1, num_channels + 1):
        ax = fig.add_subplot(num_channels, 1, chn)
        ax.set_title(channel_names[chn - 1])
        backgrounds.append(fig.canvas.copy_from_bbox(ax.bbox))  # cache the background
        # ax.axis([0, num_chunks_history * chunk_size, 1.5, 2.5])
        ax.axis([0, num_chunks_history * chunk_size, -limit, limit])
        # ax.axis([0, num_chunks_history * chunk_size, 0, 4])
        axes.append(ax)
        point_sets.append(ax.plot(np.arange(num_chunks_history * chunk_size), plot_data)[0])  # init plot content

    # Set the window position and size, this only works for Qt
    fig_manager = plt.get_current_fig_manager()
    fig_manager.window.setGeometry(50, 100, 640, 545)

    plt.show()
    plt.draw()
    fig.canvas.start_event_loop(0.001)  # otherwise plot freezes after 3-4 iterations

    RUN = True
    while RUN:
        if disp_queue.poll(0.1):
            msg = disp_queue.recv()

            if msg is None:
                continue

            data = msg[0]
            timestamp = msg[1]

            if data is not None:

                # Append to the history
                data_history.append(data)

                # Turned the queued chunks into a flat array
                sample_i = 0
                for d in data_history:
                    plot_data[sample_i:(sample_i + chunk_size), :] = d
                    sample_i = sample_i + chunk_size

                for chn in range(num_channels):
                    fig.canvas.restore_region(backgrounds[chn])  # restore background
                    point_sets[chn].set_data(np.arange(num_chunks_history * chunk_size), plot_data[:, chn])
                    axes[chn].draw_artist(point_sets[chn])  # redraw just the points
                    # fig.canvas.blit(axes[chn].bbox)                    # fill in the axes rectangle

                fig.canvas.draw()
                fig.canvas.flush_events()

            else:
                RUN = False
    # clean up
    plt.close(fig)


def plot_task_fictrac(disp_queue, fictrac_state_fields=['speed', 'direction', 'heading'], num_history=1000):
    """
    A coroutine for plotting fast, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4. This is used
    for plotting streaming data coming from FicTrac.

    :param disp_queue: The message queue from which data is sent for plotting.
    :return: None
    """

    warnings.filterwarnings("ignore", category=matplotlib.cbook.mplDeprecation)
    plt.ion()

    fig = plt.figure()
    fig.canvas.set_window_title('traces: fictrac')

    # Number of fields to display
    num_channels = len(fictrac_state_fields)

    # Axes limits for each field
    field_ax_limits = {'speed': (0, .03),
                       'direction': (0, 2 * np.pi),
                       'heading': (0, 2 * np.pi)}

    # Setup a queue for caching the historical data received so we can plot history of samples up to
    # some N
    data_history = deque([SHMEMFicTracState() for i in range(num_history)], maxlen=num_history)

    plot_data = np.zeros((num_history, num_channels))

    # We want to create a subplot for each channel
    axes = []
    backgrounds = []
    point_sets = []
    for chn in range(1, num_channels + 1):
        field_name = fictrac_state_fields[chn - 1]
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
    while RUN:
        msg = disp_queue.recv()

        if msg is None or not isinstance(msg, SHMEMFicTracState):
            continue

        cur_state = msg

        # Append to the history
        data_history.append(cur_state)

        # Turned the queued chunks into a flat array
        sample_i = 0
        for d in data_history:
            chan_i = 0
            for field in fictrac_state_fields:
                plot_data[sample_i, chan_i] = getattr(d, field)
                chan_i = chan_i + 1
            sample_i = sample_i + 1

        for chn in range(num_channels):
            fig.canvas.restore_region(backgrounds[chn])  # restore background
            point_sets[chn].set_data(np.arange(num_history), plot_data[:, chn])
            axes[chn].draw_artist(point_sets[chn])  # redraw just the points
            # fig.canvas.blit(axes[chn].bbox)                    # fill in the axes rectangle

        fig.canvas.draw()
        fig.canvas.flush_events()

    # clean up
    plt.close(fig)


def test_fictrac_plot():
    disp_task = ConcurrentTask(task=plot_task_fictrac, comms="pipe",
                               taskinitargs=[])
    disp_task.start()

    speed = 0
    dspeed = 0.01
    direction = 0
    ddir = 0.01
    num_iterations = 0
    while num_iterations < 100:
        speed = speed + dspeed
        direction = direction + ddir

        if speed > 0.16:
            dspeed = -0.02
        if speed < 0:
            speed = 0
            dspeed = 0.01

        if direction > np.pi * 2:
            ddir = -0.03
        if direction < 0:
            direction = 0
            ddir = 0.01

        state = SHMEMFicTracState()
        state.speed = speed + np.random.rand() / 10
        state.direction = direction
        state.heading = direction + np.pi / 4

        disp_task.send(state)

        num_iterations = num_iterations + 1

        time.sleep(0.01)

    disp_task.send(None)

    time.sleep(2)

    disp_task.close()


if __name__ == "__main__":
    test_fictrac_plot()
