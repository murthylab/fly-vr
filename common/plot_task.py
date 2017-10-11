import matplotlib.pyplot as plt
import warnings
import matplotlib.cbook
import numpy as np
from collections import deque

def plot_task_main(disp_queue, channel_names, chunk_size, limit, num_chunks_history=10):
    '''
    Coroutine for plotting fast, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4. This is used
    as the main function of a thread to display streaming data from a process.
    '''

    num_channels = len(channel_names)

    # Setup a queue for caching the historical data received so we can plot history of samples up to
    # some N
    data_history = deque([np.zeros((chunk_size, num_channels)) for i in range(num_chunks_history)], maxlen=num_chunks_history)

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
        ax.set_title(channel_names[chn-1])
        backgrounds.append(fig.canvas.copy_from_bbox(ax.bbox))  # cache the background
        ax.axis([0, num_chunks_history * chunk_size, -limit, limit])
        axes.append(ax)
        point_sets.append(ax.plot(np.arange(num_chunks_history * chunk_size), plot_data)[0])  # init plot content

    plt.show(False)
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
                    plot_data[sample_i:(sample_i+chunk_size),:] = d
                    sample_i = sample_i + chunk_size

                for chn in range(num_channels):
                    fig.canvas.restore_region(backgrounds[chn])         # restore background
                    point_sets[chn].set_data(np.arange(num_chunks_history*chunk_size), plot_data[:,chn])
                    axes[chn].draw_artist(point_sets[chn])              # redraw just the points
                    #fig.canvas.blit(axes[chn].bbox)                    # fill in the axes rectangle

                fig.canvas.draw()
                fig.canvas.flush_events()

            else:
                RUN = False
    # clean up
   # print("   closing plot")
    plt.close(fig)