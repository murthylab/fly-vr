import queue
import os.path
import logging

import h5py
import numpy as np

from flyvr.common import SharedState, BACKEND_FICTRAC
from flyvr.common.build_arg_parser import setup_logging, setup_experiment
from flyvr.common.mmtimer import MMTimer
from flyvr.fictrac.shmem_transfer_data import new_mmap_shmem_buffer, new_mmap_signals_buffer


class ReplayFictrac(object):

    def __init__(self, h5_path):
        self._f = h5py.File(h5_path, mode='r')
        try:
            self._ds = self._f['fictrac']['output']
        except KeyError:
            self._f.close()
            raise ValueError('h5 file does not contain fictrac output')

        self._log = logging.getLogger('flyvr.fictrac.replay')
        self._log.info('loaded %s' % h5_path)

        self._fictrac_state = new_mmap_shmem_buffer()
        self._fictrac_signals = new_mmap_signals_buffer()

        # -1 as a sentinel for derived classes
        self._send_row(-1)
        self._send_row(0)

    def _send_row(self, idx):
        """
        returns: fn, ts
        """
        if idx < 0:
            return

        r = self._ds[idx].tolist()  # to python std types (all floats)

        self._fictrac_state.del_rot_cam_vec = tuple(r[1:4])
        self._fictrac_state.del_rot_error = r[4]
        self._fictrac_state.del_rot_lab_vec = tuple(r[5:8])
        self._fictrac_state.abs_ori_cam_vec = tuple(r[8:11])
        self._fictrac_state.abs_ori_lab_vec = tuple(r[11:13])
        self._fictrac_state.posx = r[14]
        self._fictrac_state.posy = r[15]
        self._fictrac_state.heading = r[16]
        self._fictrac_state.direction = r[17]
        self._fictrac_state.speed = r[18]
        self._fictrac_state.intx = r[19]
        self._fictrac_state.inty = r[20]
        self._fictrac_state.timestamp = r[21]
        self._fictrac_state.seq_num = int(r[22])

        # write the frame counter last as the other processes
        self._fictrac_state.frame_cnt = int(r[0])

        return r[0], r[21]

    def replay(self, fps='auto'):
        if fps == 'auto':
            ts = self._ds[:, 21]
            dt = abs(np.median(np.diff(ts)))
        else:
            dt = 1. / fps

        ms = dt * 1000.

        # use a queue as a simple tick-tock threadsafe rate-limiter
        tick = queue.Queue(maxsize=1)

        self._log.info('replay at %.1fhz (dt=%.2f ms%s)' % (1. / dt, ms,
                                                            ', auto calculated from file' if fps == 'auto' else ''))

        t1 = MMTimer(int(ms), lambda: tick.put(None, block=True, timeout=min(0.5, 10.*dt)))
        t1.start(True)

        for idx in range(len(self._ds)):
            ret = self._send_row(idx)

            try:
                tick.get(timeout=1.)
            except queue.Empty:
                break

            if ret is None:
                break


class FicTracDriverReplay(object):
    """ quacks like FicTracDriver for replaying a previous experiment """

    class StateReplayFictrac(ReplayFictrac):

        def __init__(self, flyvr_shared_state, experiment, *args, **kwargs):
            self._flyvr_shared_state = flyvr_shared_state
            self._experiment = experiment
            super().__init__(*args, **kwargs)

        def _send_row(self, idx):
            if idx < 0:
                _ = self._flyvr_shared_state.signal_ready(BACKEND_FICTRAC)
            if self._flyvr_shared_state.is_stopped():
                return None
            # this updates self._flyvr_shared_state
            out = super()._send_row(idx)

            if self._experiment is not None:
                # noinspection PyProtectedMember
                self._experiment.process_state(self._fictrac_state)

            return out

    def __init__(self, config_file, *args, **kwargs):
        if not os.path.splitext(config_file)[1] == '.h5':
            raise ValueError('you must supply a previous experiment h5 file containing fictrac output')
        self._h5_path = config_file

    def run(self, options):
        setup_logging(options)

        log = logging.getLogger('flyvr.fictrac.FicTracDriverReplay')

        setup_experiment(options)
        if options.experiment:
            log.info('initialized experiment %r' % options.experiment)

        flyvr_shared_state = SharedState(options=options,
                                         logger=None,
                                         where=BACKEND_FICTRAC)
        if options.experiment:
            # noinspection PyProtectedMember
            options.experiment._set_shared_state(flyvr_shared_state)

        replay = FicTracDriverReplay.StateReplayFictrac(flyvr_shared_state,
                                                        options.experiment,
                                                        self._h5_path)
        replay.replay()  # blocks

        log.info('stopped')


def main_replay():
    import argparse
    from flyvr.common.build_arg_parser import setup_logging

    parser = argparse.ArgumentParser()
    parser.add_argument('--fps', type=float, default=0, help='play back fictrac data at this fps '
                                                             '(0 = rate at which it was recorded)')
    parser.add_argument('-v', help='Verbose output', default=False, dest='verbose', action='store_true')
    parser.add_argument('h5file', nargs=1, metavar='PATH', help='path to h5 file of previous flyvr session')

    args = parser.parse_args()
    setup_logging(args)

    r = ReplayFictrac(args.h5file[0])
    r.replay('auto' if args.fps <= 0 else args.fps)
