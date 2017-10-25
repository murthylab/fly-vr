import ctypes, os 
import numpy as np

# should go to `tools.py`
def coroutine(func):
    """ decorator that auto-initializes (calls `next(None)`) coroutines"""
    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        cr.next()
        return cr
    return start


# read ctrl file - this should also work for log files
# ctrl = np.genfromtxt('wn.txt', dtype=None, names=True, delimiter='\t')

# writing a nicely formatted log file seems more complicated

def systime():
    "return a timestamp in milliseconds (ms)"
    tics = ctypes.c_int64()
    freq = ctypes.c_int64()

    #get ticks on the internal ~2MHz QPC clock
    ctypes.windll.Kernel32.QueryPerformanceCounter(ctypes.byref(tics)) 
    #get the actual freq. of the internal ~2MHz QPC clock 
    ctypes.windll.Kernel32.QueryPerformanceFrequency(ctypes.byref(freq)) 

    t_ms = tics.value*1e3/freq.value
    return t_ms

def which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')

            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def chunker(gen, chunk_size=100):
    """
    A function that takes a generator function that outputs arbitrary size numpy arrays and turns it into a chunked
    generator function along the row axis.
    :param gen: A generator function that returns 1D or 2D numpy arrays.
    :param chunk_size: The number of elements along the first dimension to inlude in each chunk.
    :return: A generator function that returns chunks.
    """
    next_chunk = None
    curr_data_sample = 0
    curr_chunk_sample = 0
    data = None
    num_samples = 0
    while True:

        if curr_data_sample == num_samples:
            data = gen.next()
            curr_data_sample = 0
            num_samples = data.shape[0]

            # If this is our first chunk, use its dimensions to figure out the number of columns
            if next_chunk is None:
                chunk_shape = list(data.shape)
                chunk_shape[0] = chunk_size
                next_chunk = np.zeros(tuple(chunk_shape), dtype=data.dtype)

        # We want to add at most chunk_size samples to a chunk. We need to see if the current data will fit. If it does,
        # copy the whole thing. If it doesn't, just copy what will fit.
        sz = min(chunk_size-curr_chunk_sample, num_samples-curr_data_sample)
        if data.ndim == 1:
            next_chunk[curr_chunk_sample:(curr_chunk_sample + sz)] = data[curr_data_sample:(curr_data_sample + sz)]
        else:
            next_chunk[curr_chunk_sample:(curr_chunk_sample+sz), :] = data[curr_data_sample:(curr_data_sample + sz), :]

        curr_chunk_sample = curr_chunk_sample + sz
        curr_data_sample = curr_data_sample + sz

        if curr_chunk_sample == chunk_size:
            curr_chunk_sample = 0
            yield next_chunk.copy()
