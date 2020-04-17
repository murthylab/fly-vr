import mmap
import ctypes
import queue
import os.path

import h5py
import numpy as np

from flyvr.common.mmtimer import MMTimer
from flyvr.fictrac.shmem_transfer_data import SHMEMFicTracState, SHMEMFicTracSignals


class ReplayFictrac(object):

    def __init__(self, h5_path):
        self._f = h5py.File(h5_path, mode='r')
        try:
            self._ds = self._f['fictrac']['output']
        except KeyError:
            self._f.close()
            raise ValueError('h5 file does not contain fictrac output')

        shmem = mmap.mmap(-1, ctypes.sizeof(SHMEMFicTracState), "FicTracStateSHMEM")
        shmem_signals = mmap.mmap(-1, ctypes.sizeof(ctypes.c_int32), "FicTracStateSHMEM_SIGNALS")

        # noinspection PyTypeChecker
        self._fictrac_state = SHMEMFicTracState.from_buffer(shmem)
        # noinspection PyTypeChecker
        self._fictrac_signals = SHMEMFicTracSignals.from_buffer(shmem_signals)

        self._send_row(0)

    def _send_row(self, idx):
        """
        returns: fn, ts
        """
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
            ts = self._ds[:][21]
            dt = abs(np.median(np.diff(ts)))
        else:
            dt = 1. / fps

        ms = dt * 1000.

        # use a queue as a simple tick-tock threadsafe rate-limiter
        tick = queue.Queue(maxsize=1)

        print('ticking at %.1fhz (every %s ms)' % (1. / dt, ms))

        t1 = MMTimer(int(ms), lambda: tick.put_nowait(None))
        t1.start(True)

        for idx in range(len(self._ds)):
            self._send_row(idx)
            try:
                tick.get(timeout=1.)
            except queue.Empty:
                break

            if self._fictrac_signals.close_signal_var == 1:
                break


class FicTracDriverReplay(object):
    """ quacks like FicTracDriver for replaying a previous experiment """

    class StateReplayFictrac(ReplayFictrac):

        def __init__(self, state, *args, **kwargs):
            self._state = state
            super().__init__(*args, **kwargs)

        def _send_row(self, idx):
            fn, ts = super()._send_row(idx)
            if idx == 1:
                self._state.FICTRAC_READY.value = 1
            self._state.FICTRAC_FRAME_NUM.value = int(fn)

    def __init__(self, config_file, *args, **kwargs):
        if not os.path.splitext(config_file)[1] == '.h5':
            raise ValueError('you must supply a previous experiment h5 file containing fictrac output')
        self._h5_path = config_file

    def run(self, message_pipe, state):
        replay = FicTracDriverReplay.StateReplayFictrac(state, self._h5_path)
        replay.replay()
        state.FICTRAC_READY.value = 0
        state.RUN.value = 0


def main_replay():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--fps', type=float, default=0, help='play back fictrac data at this fps '
                                                             '(0 = rate at which it was recorded)')
    parser.add_argument('h5file', nargs=1, metavar='PATH', help='path to h5 file of previous flyvr session')
    args = parser.parse_args()

    r = ReplayFictrac(args.h5file[0])
    r.replay('auto' if args.fps <= 0 else args.fps)
