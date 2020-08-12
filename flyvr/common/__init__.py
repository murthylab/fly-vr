import re
import sys
import mmap
import ctypes
import logging
import traceback

import numpy as np

from flyvr.fictrac.shmem_transfer_data import new_mmap_shmem_buffer


class Dottable(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


class SHMEMFlyVRState(ctypes.Structure):
    _fields_ = [
        ('run', ctypes.c_int),
        ('runtime_error', ctypes.c_int),
        ('daq_ready', ctypes.c_int),
        ('start_daq', ctypes.c_int),
        ('fictrac_ready', ctypes.c_int),
        ('daq_output_num_samples_written', ctypes.c_int),
        ('sound_output_num_samples_written', ctypes.c_int),
    ]


# noinspection PyPep8Naming
class SharedState(object):
    """
    A class to represent the shared state between our concurrent tasks. We can add values to this shared state and they
    will be passed as an argument to all tasks. This allows us to communicate with thread safe shared variables.
    """

    def __init__(self, options, logger):
        # Lets store the options passed to the program.
        self._options = options
        self._logger = logger

        # noinspection PyTypeChecker
        buf = mmap.mmap(-1,
                        ctypes.sizeof(SHMEMFlyVRState),
                        "FlyVRStateSHMEM",
                        access=mmap.ACCESS_WRITE)
        # print('Shared State: 0x%x' % ctypes.addressof(ctypes.c_void_p.from_buffer(buf)))
        self._shmem_state = SHMEMFlyVRState.from_buffer(buf)
        self._fictrac_shmem_state = new_mmap_shmem_buffer()

        # on unix (mmap) and windows (CreateFileMapping) initialize the memory block to zero upon creation

    @property
    def SOUND_OUTPUT_NUM_SAMPLES_WRITTEN(self):
        """ total number of sound samples written """
        return self._shmem_state.sound_output_num_samples_written

    @SOUND_OUTPUT_NUM_SAMPLES_WRITTEN.setter
    def SOUND_OUTPUT_NUM_SAMPLES_WRITTEN(self, v):
        self._shmem_state.sound_output_num_samples_written = int(v)

    @property
    def DAQ_OUTPUT_NUM_SAMPLES_WRITTEN(self):
        """ total number of samples written to the DAQ """
        return self._shmem_state.daq_output_num_samples_written

    @DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.setter
    def DAQ_OUTPUT_NUM_SAMPLES_WRITTEN(self, v):
        self._shmem_state.daq_output_num_samples_written = int(v)

    @property
    def FICTRAC_READY(self):
        """ FicTrac is running an processing frames """
        return self._shmem_state.fictrac_ready

    @FICTRAC_READY.setter
    def FICTRAC_READY(self, v):
        self._shmem_state.fictrac_ready = int(v)

    @property
    def FICTRAC_FRAME_NUM(self):
        """ FicTrac frame number """
        return self._fictrac_shmem_state.frame_cnt

    @property
    def START_DAQ(self):
        """ DAQ should start playback and acquisition """
        return self._shmem_state.start_daq

    @START_DAQ.setter
    def START_DAQ(self, v):
        self._shmem_state.start_daq = int(v)

    @property
    def RUN(self):
        """ the current run state """
        # XOR with 1 because this must be init to true in a safe manner yet the underlying memory block is
        # initialized to zero
        return self._shmem_state.run ^ 1

    @RUN.setter
    def RUN(self, v):
        self._shmem_state.run = int(v) ^ 1

    @property
    def RUNTIME_ERROR(self):
        """  a value to indicate a runtime error occurred and the whole of flyvr program should close """
        return self._shmem_state.runtime_error

    @RUNTIME_ERROR.setter
    def RUNTIME_ERROR(self, v):
        self._shmem_state.runtime_error = int(v)

    @property
    def DAQ_READY(self):
        """ the daq is aquiring samples """
        return self._shmem_state.daq_ready

    @DAQ_READY.setter
    def DAQ_READY(self, v):
        self._shmem_state.daq_ready = int(v)

    @property
    def logger(self):
        """ an object which provides and interface for sending logging messages to the logging process """
        return self._logger

    @property
    def options(self):
        """ runtime / command line config options """
        return self._options

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
        return self.RUNTIME_ERROR == 0 and self.RUN != 0

    def runtime_error(self, excep, error_code):
        sys.stderr.write("RUNTIME ERROR - Unhandled Exception: \n" + str(excep) + "\n")
        traceback.print_exc()
        self.RUN = 0
        self.RUNTIME_ERROR = -1


class Every(object):
    def __init__(self, n):
        self._i = 0
        self.n = n

    def __nonzero__(self):
        r = (self._i % self.n) == 0
        self._i += 1
        return r


class Randomizer(object):

    MODE_SHUFFLE = 'shuffle'
    MODE_RANDOM_WALK = 'random_walk'
    MODE_RANDOM_WALK_NON_REPEAT = 'random_walk_non_repeat'
    MODE_NONE = 'none'

    IN_PLAYLIST_IDENTIFIER = '_options'

    def __init__(self, *items, mode=MODE_NONE, repeat=1, random_seed=None):
        self._r = np.random.RandomState(seed=random_seed)
        self._mode = mode
        self._items = items

        if mode == Randomizer.MODE_NONE:
            self._items = items
        elif mode == Randomizer.MODE_SHUFFLE:
            _items = list(items)
            self._r.shuffle(_items)
            self._items = tuple(_items)
        elif mode in (Randomizer.MODE_RANDOM_WALK, Randomizer.MODE_RANDOM_WALK_NON_REPEAT):
            # handled in the iter below
            pass
        else:
            raise ValueError('unknown mode: %s' % mode)

        if not isinstance(repeat, int) and (repeat >= 1):
            raise ValueError('repeat must be an integer >= 1')

        self._repeat = repeat
        self._log = logging.getLogger('flyvr.common.Randomizer')

    @classmethod
    def new_from_playlist_option_item(cls, option_item_defn, *items):
        if option_item_defn:
            id_, defn = option_item_defn.popitem()
            if id_ == Randomizer.IN_PLAYLIST_IDENTIFIER:
                return cls(*items,
                           mode=defn.get('random_mode', Randomizer.MODE_NONE),
                           repeat=int(defn.get('repeat', 1)),
                           random_seed=defn.get('random_seed', None))

        return cls(*items)

    def __repr__(self):
        import textwrap
        return "<Randomizer(%s,mode=%s,repeat=%s>" % (
            textwrap.shorten(', '.join(str(i) for i in self._items),
                             width=25), self._mode, self._repeat)

    def _random_walk(self):
        for _ in self._items:
            yield self._r.choice(self._items)

    def _repeating_iter(self):
        if self._mode == Randomizer.MODE_RANDOM_WALK:
            for _ in range(self._repeat * len(self._items)):
                yield self._r.choice(self._items)
        elif self._mode == Randomizer.MODE_RANDOM_WALK_NON_REPEAT:
            n = 0
            last = None
            while n < (self._repeat * len(self._items)):
                v = last
                while v == last:
                    v = self._r.choice(self._items)

                yield v

                last = v
                n += 1
        else:
            for _ in range(self._repeat):
                for i in self._items:
                    yield i

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

