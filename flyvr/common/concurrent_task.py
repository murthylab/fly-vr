import time
import sys

from multiprocessing import Process, Pipe, Manager
# noinspection PyUnresolvedReferences
from multiprocessing.dummy import Process as _DummyProcess, Queue as _DummyQueue, Pipe as _DummyPipe


class _DummyProcessDaemonThread(_DummyProcess):
    daemon = True


class ConcurrentTask(object):

    """
    The ConcurrentTask class encapsulates functionality for creating, starting, stopping, and communicating with
    a process thread. This class is basically a wrapper of multiprocessing.Process that allows for two different
    communication methods, pipes and queues, to use the same interface. Queue communication is useful when we want to
    ensure the underlying process will finnish processing all data sent to it before terminating. If you don't care
    about this, pipe should be fine.
    """

    process_cls = Process
    manager_cls = Manager

    @classmethod
    def get_comms(cls, comms, manager_cls):
        if comms == 'pipe':
            return Pipe()
        elif comms == 'queue':
            return manager_cls().Queue()
        else:
            raise NotImplementedError

    def __init__(self, task, taskinitargs=(), comms='queue'):
        """
        Create the underlying data structures for running the task, but do not start it.

        :param task: A callable object to be invoked by Process.run
        :param taskinitargs: A list of arguments to pass to task
        :param comms: Either 'queue' or 'pipe'
        :raise ValueError: comms must either be 'queue' or 'pipe'
        """

        # task (function(pip/queue, getfun, *args)), task init args, queue/pipe
        if comms == "pipe":
            self._sender, self._receiver = self.get_comms('pipe', manager_cls=self.manager_cls)
        elif comms == "queue":
            self._receiver = self._sender = self.get_comms('queue', manager_cls=self.manager_cls)
        elif comms is None:
            self._sender = self._receiver = None
        else:
            raise ValueError("comms argument must either be 'queue' or 'pipe'")

        self.comms = comms

        self._task_repr = repr(task)

        taskinitargs = list(taskinitargs)
        if self._receiver is not None:
            taskinitargs.insert(0, self._receiver)  # prepend queue, i.e. sink end of pipe or end of queue
        self._process = self.process_cls(target=task, args=tuple(taskinitargs))

    def __repr__(self):
        return "<%s(task=%s, comms=%s>" % (self.__class__.__name__, self._task_repr, self.comms)

    def send(self, data):
        """
        Send data to the process using the underlying communication mechanism specified in the the constructor.

        :param data: The data object that should be passed to the process.
        """
        if self._sender is None:
            return

        if self.comms == "queue":
            self._sender.put(data)
        elif self.comms == "pipe":
            self._sender.send(data)

    @property
    def sender(self):
        return self._sender

    def is_alive(self):
        return self._process.is_alive()

    def start(self):
        """
        Call start on the underlying multiprocessing.Process object.
        """
        self._process.start()

    def finish(self, verbose=False, sleepduration=1, sleepcycletimeout=5, maxsleepcycles=100000000):
        """

        :param verbose:
        :param sleepduration:
        :param sleepcycletimeout:
        :param maxsleepcycles:
        :return:
        """
        if self.comms == "queue":
            sleepcounter = 0
            queuesize = self._sender.qsize()
            queuehasnotchangedcounter = 0
            while queuesize > 0 and sleepcounter < maxsleepcycles and queuehasnotchangedcounter < sleepcycletimeout:
                time.sleep(sleepduration)
                queuesize = self._sender.qsize()
                sleepcounter += 1
                queuehasnotchanged = (queuesize == self._sender.qsize())
                if queuehasnotchanged:
                    queuehasnotchangedcounter += 1
                else:
                    queuehasnotchangedcounter = 0
                if verbose:
                    sys.stdout.write('\r   waiting {} seconds for {} frames to self.'.format(
                        sleepcounter, self._sender.qsize()))  # frame interval in ms

    def close(self):
        self.send(None)
        time.sleep(0.5)

        try:
            self._process.terminate()
        except AttributeError:
            # multiprocessing.dummy
            pass

        time.sleep(0.5)

        if self.comms != "queue":
            if self._sender is not None:
                self._sender.close()

            if self._receiver is not None:
                self._receiver.close()


class ConcurrentTaskThreaded(ConcurrentTask):

    process_cls = _DummyProcessDaemonThread
    manager_cls = None

    @classmethod
    def get_comms(cls, comms, manager_cls):
        if comms == 'pipe':
            return _DummyPipe()
        elif comms == 'queue':
            return _DummyQueue()
        else:
            raise NotImplementedError
