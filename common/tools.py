import ctypes, os 
# import numpy as np

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