import ctypes
import warnings
import collections

import numpy as np
import matplotlib.pyplot as plt

from flyvr.fictrac.shmem_transfer_data import SHMEMFicTracState, new_mmap_shmem_buffer

FIELD_AX_LIMITS = {'speed': (0, .05),
                   'direction': (0, 2 * np.pi),
                   'heading': (0, 2 * np.pi),
                   'heading_diff': (0, 0.261799),
                   'del_rot_error': (0, 15000),
                   'del_rot_cam_vec0': (-0.025, 0.025),
                   'del_rot_cam_vec1': (-0.025, 0.025),
                   'del_rot_cam_vec2': (-0.025, 0.025),
                   'del_rot_cam_vec_magn': (0, 0.1),
                   'abs_ori_cam_vec0': (-np.pi, np.pi),
                   'abs_ori_cam_vec1': (-np.pi, np.pi),
                   'abs_ori_cam_vec2': (-np.pi, np.pi),
                   }


def magnitude(vector):
    return np.sqrt(sum(pow(element, 2) for element in vector))


def angle_diff(angle1, angle2):
    diff = angle2 - angle1
    while diff < np.deg2rad(-180.0):
        diff += np.deg2rad(360.0)
    while diff > np.deg2rad(180):
        diff -= np.deg2rad(360.0)
    return diff


def plot_task_fictrac(disp_queue, flyvr_state,
                      fictrac_state_fields=('speed', 'direction', 'del_rot_cam_vec1', 'del_rot_error'),
                      num_history=200,
                      fig=None):
    """
    A coroutine for plotting fast, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4. This is used
    for plotting streaming data coming from FicTrac.
    """

    import matplotlib.cbook
    warnings.filterwarnings("ignore", category=matplotlib.cbook.mplDeprecation)

    # see note below about MPL finnicky
    # plt.ion()

    fig = plt.figure() if fig is None else fig
    fig.canvas.set_window_title('traces: fictrac')

    # Number of fields to display
    num_channels = len(fictrac_state_fields)

    # Setup a queue for caching the historical data received so we can plot history of samples up to
    # some N
    data_history = collections.deque([SHMEMFicTracState() for _ in range(num_history)], maxlen=num_history)

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
        ax.axis([0, num_history, FIELD_AX_LIMITS[field_name][0], FIELD_AX_LIMITS[field_name][1]])
        axes.append(ax)
        point_sets.append(ax.plot(np.arange(num_history), plot_data)[0])  # init plot content

    # while testing on win10 shows this isn't necessary with current MPL backend, MPL has always been
    # super flaky about non-interactive realtime plotting across multiple platforms, so the figure based API could
    # stop working at basically any point in my experience
    # plt.show()
    # plt.draw()

    fig.canvas.draw()
    fig.canvas.start_event_loop(0.001)  # otherwise plot freezes after 3-4 iterations
    fig.show()

    data = new_mmap_shmem_buffer()
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
                    if field == 'del_rot_cam_vec_magn':
                        plot_data[sample_i, chan_i] = magnitude(last_d.del_rot_cam_vec)
                    elif field.endswith('_diff'):
                        real_field = field.replace('_diff', '')

                        if real_field in ['heading', 'direction']:
                            plot_data[sample_i, chan_i] = abs(
                                angle_diff(getattr(d, real_field), getattr(last_d, real_field)))
                        else:
                            plot_data[sample_i, chan_i] = getattr(d, real_field) - getattr(last_d, real_field)
                    elif field.endswith('vec0'):
                        plot_data[sample_i, chan_i] = getattr(d, field[:-1])[0]
                    elif field.endswith('vec1'):
                        plot_data[sample_i, chan_i] = getattr(d, field[:-1])[1]
                    elif field.endswith('vec2'):
                        plot_data[sample_i, chan_i] = getattr(d, field[:-1])[2]
                    else:
                        plot_data[sample_i, chan_i] = getattr(d, field)

                    chan_i = chan_i + 1
                last_d = d
                sample_i = sample_i + 1

            for chn in range(num_channels):
                fig.canvas.restore_region(backgrounds[chn])  # restore background
                point_sets[chn].set_data(np.arange(num_history), plot_data[:, chn])
                axes[chn].draw_artist(point_sets[chn])  # redraw just the points
                # fig.canvas.blit(axes[chn].bbox)                    # fill in the axes rectangle

            fig.canvas.draw()
            fig.canvas.flush_events()

    # clean up
    # plt.close(fig)


def main_plot_fictrac():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--plot', help='fictrac state variable to plot',
                        default=('speed', 'direction', 'del_rot_cam_vec_magn', 'del_rot_error'),
                        nargs="*", choices=list(FIELD_AX_LIMITS.keys()))
    args = parser.parse_args()

    class _MockState(object):
        def is_running_well(self):
            return True

    plot_task_fictrac(None, _MockState(),
                      fictrac_state_fields=args.plot)
