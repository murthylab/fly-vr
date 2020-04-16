from ctypes import *
from ctypes.wintypes import UINT
from ctypes.wintypes import DWORD

timeproc = WINFUNCTYPE(None, c_uint, c_uint, DWORD, DWORD, DWORD)
timeSetEvent = windll.winmm.timeSetEvent
timeKillEvent = windll.winmm.timeKillEvent


class MMTimer:
    """
    A simple class that invokes a control function at regular intervals. It uses the Windows Multimedia Timer. Code
    taken from this stackoverflow post:

    https://stackoverflow.com/questions/10717589/how-to-implement-high-speed-consistent-sampling

    """

    def _tick(self):
        self.tickFunc()

        if not self.periodic:
            self.stop()

    def _callback(self, uID, uMsg, dwUser, dw1, dw2):
        if self.running:
            self._tick()

    def __init__(self, interval, tickFunc, stopFunc=None, resolution=0, periodic=True):
        """
        Setup a control to be invoked on a fixed interval.

        :param interval: How frequently in milliseconds to invoke the control.
        :param tickFunc: The control function to invoke.
        :param stopFunc: Another control to invoke when the event is stopped.
        :param resolution: The resolution of the time.
        :param periodic: Keep invoking the call back or not?
        """
        self.interval = UINT(interval)
        self.resolution = UINT(resolution)
        self.tickFunc = tickFunc
        self.stopFunc = stopFunc
        self.periodic = periodic
        self.id = None
        self.running = False
        self.calbckfn = timeproc(self._callback)

    def start(self, instant=False):
        """
        Start the timer.

        :param instant: Call the control instantly the first time
        :return: None
        """
        if not self.running:
            self.running = True
            if instant:
                self._tick()

            self.id = timeSetEvent(self.interval, self.resolution,
                                   self.calbckfn, c_ulong(0),
                                   c_uint(self.periodic))

    def stop(self):
        """
        Stop the timer control.

        :return: None
        """
        if self.running:
            timeKillEvent(self.id)
            self.running = False

            if self.stopFunc:
                self.stopFunc()


def main():
    from .mmtimer import MMTimer
    import time

    def tick():
        print(("{0:.4f}".format(time.clock() * 1000)))

    t1 = MMTimer(40, tick)
    time.clock()
    t1.start(True)
    time.sleep(20)
    t1.stop()


if __name__ == "__main__":
    main()
