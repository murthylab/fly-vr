import matplotlib.pyplot as plt
import numpy as np

plt.ion()

def plot_task_main(disp_queue, channel):
    '''
    Coroutine for plotting fast, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4. This is used
    as the main function of a thread to display streaming data from a process.
    '''
    plt.ion()
    fig = plt.figure()
    fig.canvas.set_window_title('traces: daq')
    ax = fig.add_subplot(111)
    plt.show(False)
    plt.draw()
    fig.canvas.start_event_loop(0.001)  # otherwise plot freezes after 3-4 iterations
    bgrd = fig.canvas.copy_from_bbox(ax.bbox)  # cache the background
    points = ax.plot(np.arange(10000), np.zeros((10000, 1)))[0]  # init plot content
    RUN = True
    ax.axis([0, 10000, -25, 25])
    while RUN:
        if disp_queue.poll(0.1):
            data = disp_queue.recv()
            if data is not None:
                # print("    plotting {0}".format(data[0].shape))
                fig.canvas.restore_region(bgrd)  # restore background
                # for chn in range(data[0].shape[1]):
                points.set_data(np.arange(10000), data[0][:10000, channel])
                ax.draw_artist(points)           # redraw just the points
                fig.canvas.blit(ax.bbox)         # fill in the axes rectangle
                #ax.relim()
                #ax.autoscale_view()                 # rescale the y-axis
                fig.canvas.draw()
                fig.canvas.flush_events()
            else:
                RUN = False
    # clean up
   # print("   closing plot")
    plt.close(fig)