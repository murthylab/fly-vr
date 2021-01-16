import re
import sys
import mmap
import time
import ctypes
import logging
import itertools
import threading

import numpy as np

from flyvr.fictrac.shmem_transfer_data import new_mmap_shmem_buffer
from flyvr.common.ipc import Sender, Reciever, RELAY_SEND_PORT, RELAY_RECIEVE_PORT, RELAY_HOST, CommonMessages


BACKEND_VIDEO = "video"
BACKEND_AUDIO = "audio"
BACKEND_DAQ = "daq"

BACKEND_HWIO = "hwio"
BACKEND_FICTRAC = "fictrac"


class SHMEMFlyVRState(ctypes.Structure):
    _fields_ = [
        ('daq_output_num_samples_written', ctypes.c_int),
        ('daq_input_num_samples_read', ctypes.c_int),
        ('sound_output_num_samples_written', ctypes.c_int),
        ('video_output_num_frames', ctypes.c_int),
    ]


# noinspection PyPep8Naming
class SharedState(object):
    """
    A class to represent the shared state between our concurrent tasks. We can add values to this shared state and they
    will be passed as an argument to all tasks. This allows us to communicate with thread safe shared variables.
    """

    def __init__(self, options, logger, where='', _start_rx_thread=True):
        self._options = options
        self._logger = logger

        self._log = logging.getLogger('flyvr.common.SharedState%s' % (("(in='" + where + "')") if where else ''), )

        # noinspection PyTypeChecker
        buf = mmap.mmap(-1,
                        ctypes.sizeof(SHMEMFlyVRState),
                        "FlyVRStateSHMEM",
                        access=mmap.ACCESS_WRITE)
        # print('Shared State: 0x%x' % ctypes.addressof(ctypes.c_void_p.from_buffer(buf)))
        self._shmem_state = SHMEMFlyVRState.from_buffer(buf)
        self._fictrac_shmem_state = new_mmap_shmem_buffer()
        # on unix (mmap) and windows (CreateFileMapping) initialize the memory block to zero upon creation

        self._backends_ready = set()
        self._evt_start = threading.Event()
        self._evt_stop = threading.Event()

        self._rx = Reciever(host=RELAY_HOST, port=RELAY_RECIEVE_PORT, channel=b'')
        if _start_rx_thread:
            self._t_rx = threading.Thread(target=self._ipc_rx, daemon=True)
            self._t_rx.start()

        self._tx = Sender.new_for_relay(host=RELAY_HOST, port=RELAY_SEND_PORT, channel=b'')

    def _ipc_rx(self):
        while True:
            msg = self._rx.get_next_element()
            if msg:
                if CommonMessages.EXPERIMENT_START in msg:
                    self._evt_start.set()
                if CommonMessages.EXPERIMENT_STOP in msg:
                    self._evt_stop.set()
                if CommonMessages.READY in msg:
                    self._backends_ready.add(msg[CommonMessages.READY])

    def wait_for_start(self, timeout=180):
        if (self._options is not None) and self._options.wait:
            self._log.info('waiting %ss for start signal' % timeout)
            return self._evt_start.wait(timeout=timeout)
        else:
            return True

    def is_started(self):
        return self._evt_start.is_set()

    def is_stopped(self):
        return self._evt_stop.is_set()

    def is_backend_ready(self, backend):
        return backend in self._backends_ready

    @property
    def backends_ready(self):
        return tuple(sorted(self._backends_ready))

    def wait_for_backends(self, *backends, timeout=60):
        self._log.info('waiting %ss for %r backends' % (timeout, backends))

        t0 = time.time()
        for i in itertools.count():
            if all(b in self._backends_ready for b in backends):
                return True

            time.sleep(0.5)

            t = time.time()
            if t > (t0 + timeout):
                break

            if (i % 10) == 0:
                not_ready = set(backends) - set(self._backends_ready)
                self._log.debug('not ready backends: %r' % (not_ready, ))

        not_ready = set(backends) - set(self._backends_ready)
        self._log.warning('after %ss the following backends were not ready: %r' % (timeout, not_ready))

        return False

    def _signal_thread(self, sender, msg, timeout):
        t0 = time.time()
        for i in itertools.count():
            sender.process(**msg)

            time.sleep(0.5)

            t = time.time()
            if t > (t0 + timeout):
                break

            if (i % 10) == 0:
                self._log.debug('signaling %r' % (msg, ))

        sender.close()

    def _build_toc_message(self, backend):
        return {'backend': backend,
                'sound_output_num_samples_written': self._shmem_state.sound_output_num_samples_written,
                'video_output_num_frames': self._shmem_state.video_output_num_frames,
                'daq_output_num_samples_written': self._shmem_state.daq_output_num_samples_written,
                'daq_input_num_samples_read': self._shmem_state.daq_input_num_samples_read,
                'fictrac_frame_num': self._fictrac_shmem_state.frame_cnt,
                'time_ns': time.time_ns()}

    def signal_new_playlist_item(self, identifier, backend, **extra):
        msg = self._build_toc_message(backend)
        msg.update(extra)
        self._tx.process(**CommonMessages.build(CommonMessages.EXPERIMENT_PLAYLIST_ITEM, identifier, **msg))

    def signal_ready(self, what):
        self._log.info('signaling %s ready' % what)
        t = threading.Thread(target=self._signal_thread,
                             args=(Sender.new_for_relay(host=RELAY_HOST, port=RELAY_SEND_PORT, channel=b''),
                                   CommonMessages.build(CommonMessages.READY, what),
                                   20),
                             daemon=True)
        t.start()
        return t

    def signal_start(self):
        self._log.info('signaling start')
        t = threading.Thread(target=self._signal_thread,
                             args=(Sender.new_for_relay(host=RELAY_HOST, port=RELAY_SEND_PORT, channel=b''),
                                   CommonMessages.build(CommonMessages.EXPERIMENT_START, ''),
                                   2),
                             daemon=True)
        t.start()
        return t

    def signal_stop(self):
        self._log.info('signaling stop')
        t = threading.Thread(target=self._signal_thread,
                             args=(Sender.new_for_relay(host=RELAY_HOST, port=RELAY_SEND_PORT, channel=b''),
                                   CommonMessages.build(CommonMessages.EXPERIMENT_STOP, ''),
                                   2),
                             daemon=True)
        t.start()
        return t

    @property
    def SOUND_OUTPUT_NUM_SAMPLES_WRITTEN(self):
        """ total number of sound samples written """
        return self._shmem_state.sound_output_num_samples_written

    @SOUND_OUTPUT_NUM_SAMPLES_WRITTEN.setter
    def SOUND_OUTPUT_NUM_SAMPLES_WRITTEN(self, v):
        self._shmem_state.sound_output_num_samples_written = int(v)

    @property
    def VIDEO_OUTPUT_NUM_FRAMES(self):
        """ total number of video frames shown """
        return self._shmem_state.video_output_num_frames

    @VIDEO_OUTPUT_NUM_FRAMES.setter
    def VIDEO_OUTPUT_NUM_FRAMES(self, v):
        self._shmem_state.video_output_num_frames = int(v)

    @property
    def DAQ_OUTPUT_NUM_SAMPLES_WRITTEN(self):
        """ total number of samples written to the DAQ """
        return self._shmem_state.daq_output_num_samples_written

    @DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.setter
    def DAQ_OUTPUT_NUM_SAMPLES_WRITTEN(self, v):
        self._shmem_state.daq_output_num_samples_written = int(v)

    @property
    def DAQ_INPUT_NUM_SAMPLES_READ(self):
        """ total number of samples read on the DAQ """
        return self._shmem_state.daq_input_num_samples_read

    @DAQ_INPUT_NUM_SAMPLES_READ.setter
    def DAQ_INPUT_NUM_SAMPLES_READ(self, v):
        self._shmem_state.daq_input_num_samples_read = int(v)

    @property
    def FICTRAC_FRAME_NUM(self):
        """ FicTrac frame number """
        return self._fictrac_shmem_state.frame_cnt

    @property
    def logger(self):
        """ an object which provides and interface for sending logging messages to the logging process """
        return self._logger

    def _iter_state(self):
        for n in dir(self):
            if re.match(r"""[A-Z]+""", n):
                yield n, getattr(self, n)

    def print_state(self, out=None):
        out = sys.stdout if out is None else out
        out.write('\033[2J')
        for n, v in self._iter_state():
            out.write(f'{n}: {v}\n')
        out.flush()

    def is_running_well(self):
        return True

    def runtime_error(self, errno):
        pass


class Every(object):
    def __init__(self, n):
        self._i = 0
        self.n = n

    def __nonzero__(self):
        r = (self._i % self.n) == 0
        self._i += 1
        return r


class Randomizer(object):

    MODE_NONE = 'none'
    MODE_SHUFFLE = 'shuffle'
    MODE_SHUFFLE_NON_REPEAT = 'shuffle_non_repeat'
    MODE_RANDOM_WALK = 'random_walk'
    MODE_RANDOM_WALK_NON_CONSECUTIVE = 'random_walk_non_consecutive'

    IN_PLAYLIST_IDENTIFIER = '_options'

    REPEAT_FOREVER = sys.maxsize

    def __init__(self, *items, mode=MODE_NONE, repeat=1, random_seed=None):
        self._r = np.random.RandomState(seed=random_seed)
        self._mode = mode
        self._items = items

        self.__original_items = tuple(items)
        self.__original_random_seed = random_seed
        self.__original_repeat = repeat

        if mode == Randomizer.MODE_NONE:
            self._items = items
        elif mode == Randomizer.MODE_SHUFFLE:
            _items = list(items)
            self._r.shuffle(_items)
            self._items = tuple(_items)
        elif mode in (Randomizer.MODE_RANDOM_WALK, Randomizer.MODE_RANDOM_WALK_NON_CONSECUTIVE,
                      Randomizer.MODE_SHUFFLE_NON_REPEAT):
            # handled in the iter below
            pass
        else:
            raise ValueError('unknown mode: %s' % mode)

        if not isinstance(repeat, int) and (repeat >= 1):
            raise ValueError('repeat must be an integer >= 1')

        self._repeat = repeat
        self._log = logging.getLogger('flyvr.common.Randomizer')

    @classmethod
    def new_from_playlist_option_item(cls, option_item_defn, *items, **defaults):
        if option_item_defn:
            id_, defn = option_item_defn.popitem()
            if id_ == Randomizer.IN_PLAYLIST_IDENTIFIER:
                return cls(*items,
                           mode=defn.get('random_mode', defaults.get('mode', Randomizer.MODE_NONE)),
                           repeat=int(defn.get('repeat', defaults.get('repeat', 1))),
                           random_seed=defn.get('random_seed', defaults.get('random_seed', None)))

        return cls(*items, **defaults)

    def __repr__(self):
        import textwrap

        return "<Randomizer([%s],mode=%s,repeat=%s>" % (textwrap.shorten(', '.join(str(i) for i in self._items),
                                                                         width=25),
                                                        self._mode,
                                                        'forever' if self.repeat_forever else self._repeat)

    def _random_walk(self):
        for _ in self._items:
            yield self._r.choice(self._items)

    def _repeating_iter(self):
        if self._mode == Randomizer.MODE_RANDOM_WALK:
            for _ in range(self._repeat * len(self._items)):
                yield self._r.choice(self._items)
        elif self._mode == Randomizer.MODE_RANDOM_WALK_NON_CONSECUTIVE:
            n = 0
            last = None
            while n < (self._repeat * len(self._items)):
                v = last
                while v == last:
                    v = self._r.choice(self._items)

                yield v

                last = v
                n += 1
        elif self._mode == Randomizer.MODE_SHUFFLE_NON_REPEAT:
            for _ in range(self._repeat):
                _items = list(self._items)
                self._r.shuffle(_items)
                for i in _items:
                    yield i
        else:
            for _ in range(self._repeat):
                for i in self._items:
                    yield i

    @property
    def repeat_forever(self):
        return self._repeat == Randomizer.REPEAT_FOREVER

    def _copy_thyself(self, mode=None, repeat=None, random_seed=-1):
        # anytime you use this it could be dangerous because this class is predominately used inside
        # AudioStimPlaylist which has generators that are initialised and hold state outside of their
        # iteration, so swapping out their internal randomizer might have consequences. this function
        # is only basically to plot the 1D signal from audio/daq playlists
        return Randomizer(*self.__original_items,
                          mode=mode if mode is not None else self._mode,
                          repeat=repeat if repeat is not None else self.__original_repeat,
                          random_seed=random_seed if random_seed != -1 else self.__original_random_seed)

    def iter_items(self):
        return self._repeating_iter()


def main_print_state():
    import time
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--forever', action='store_true',
                        help='print state continuously (default is to print once and exit)')
    args = parser.parse_args()

    s = SharedState(None, None)

    while True:
        s.print_state()
        if args.forever:
            time.sleep(1)
        else:
            break

