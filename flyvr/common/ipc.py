import pickle
import threading

import zmq


class CommonMessages(object):

    QUIT = 'quit'
    READY = 'ready'
    ERROR = 'error'
    FINISHED = 'finished'
    EXPERIMENT_STOP = 'stop'
    EXPERIMENT_START = 'start'
    EXPERIMENT_PLAYLIST_ITEM = 'item'

    @staticmethod
    def build(msg, value, **extra):
        m = {msg: value}
        m.update(extra)
        return m


class _ZMQMultipartSender(object):
    def __init__(self, host, port, channel, bind=True):
        ctx = zmq.Context()

        # fixme: IPC will be supported on windows beginning with next zmq release
        stream_address = "tcp://%s:%d" % (host, port)

        # noinspection PyUnresolvedReferences
        sock = ctx.socket(zmq.PUB)

        if bind:
            sock.bind(stream_address)
        else:
            sock.connect(stream_address)

        self._channel = channel
        self._stream = sock

    def _send(self, data):
        # noinspection PyUnresolvedReferences
        self._stream.send_multipart((self._channel, data), zmq.NOBLOCK)


class Sender(_ZMQMultipartSender):

    @classmethod
    def new_for_relay(cls, **kwargs):
        return cls(**kwargs, bind=False)

    def process(self, **data):
        self._send(memoryview(pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)))

    def close(self, block=True):
        self._stream.close(linger=-1 if block else 0)


class PlaylistSender(Sender):

    HOST = '127.0.0.1'
    PORT = 6444
    PUB_CHANNEL = b'p'

    def __init__(self):
        super().__init__(self.HOST, self.PORT, self.PUB_CHANNEL)


class Reciever(object):

    # noinspection PyUnresolvedReferences
    def __init__(self, host, port, channel):
        ctx = zmq.Context()
        address = "tcp://%s:%d" % (host, port)
        sock = ctx.socket(zmq.SUB)
        sock.connect(address)
        sock.setsockopt(zmq.LINGER, 0)
        sock.setsockopt_string(zmq.SUBSCRIBE, channel.decode())
        self.stream = sock

    def get_next_element(self):
        while True:
            _, msg = self.stream.recv_multipart()
            state = pickle.loads(msg)
            if (not state) or (not isinstance(state, dict)):
                return {}
            return state


class PlaylistReciever(Reciever):

    # noinspection PyUnusedLocal
    def __init__(self, **kwargs):
        super().__init__(host=PlaylistSender.HOST, port=PlaylistSender.PORT, channel=PlaylistSender.PUB_CHANNEL)


class Mirror(threading.Thread):

    daemon = True

    def __init__(self, host, port, channel):
        threading.Thread.__init__(self)
        self._lock = threading.Lock()
        self._state = {}
        self._streamer = Reciever(host=host, port=port, channel=channel)

    def __getitem__(self, item):
        return self._state[item]

    def run(self):
        while True:
            _, msg = self._streamer.stream.recv_multipart()
            with self._lock:
                if msg:
                    state = pickle.loads(msg)
                    if state and isinstance(state, dict):
                        self._state.update(state)


class PlaylistMirror(Mirror):

    # noinspection PyUnusedLocal
    def __init__(self, **kwargs):
        super().__init__(host=PlaylistSender.HOST, port=PlaylistSender.PORT, channel=PlaylistSender.PUB_CHANNEL)


RELAY_HOST = '127.0.0.1'
RELAY_SEND_PORT = 6454
RELAY_RECIEVE_PORT = 6455


def run_main_relay(_ctx=None):
    # blocks

    context = _ctx if _ctx is not None else zmq.Context()

    # socket facing producers
    # noinspection PyUnresolvedReferences
    frontend = context.socket(zmq.XPUB)
    frontend.bind("tcp://%s:%s" % (RELAY_HOST, RELAY_RECIEVE_PORT))

    # socket facing consumers
    # noinspection PyUnresolvedReferences
    backend = context.socket(zmq.XSUB)
    backend.bind("tcp://%s:%s" % (RELAY_HOST, RELAY_SEND_PORT))

    # noinspection PyUnresolvedReferences
    zmq.proxy(frontend, backend)

    # we never get here
    frontend.close()
    backend.close()
    context.term()


def main_relay():
    # zmq blocking calls eat ctrl+c on windows, which means this command line entry is
    # not ctrl+c killable. To make it so, run it instead in a daemon thread and use a zmq interrupt
    # override to let us catch the ctrl+c and break out of the indefinite wait on the quit event

    # noinspection PyPackageRequirements
    from zmq.utils.win32 import allow_interrupt

    quit_evt = threading.Event()

    # noinspection PyUnusedLocal
    def ctrlc(*args):
        quit_evt.set()

    t = threading.Thread(target=run_main_relay, daemon=True)
    t.start()

    with allow_interrupt(action=ctrlc):
        try:
            quit_evt.wait()
        except KeyboardInterrupt:
            pass


def main_ipc_send():
    import json
    import time
    import argparse

    from flyvr.common.build_arg_parser import setup_logging
    from flyvr.common import SharedState

    parser = argparse.ArgumentParser()
    parser.add_argument('-v', help='Verbose output', default=False, dest='verbose', action='store_true')
    parser.add_argument('--start', action='store_true', help='send start signal')
    parser.add_argument('--stop', action='store_true', help='send stop signal')
    parser.add_argument('json', nargs='?', help='raw json message contents (see README)')
    args = parser.parse_args()

    if args.start:
        setup_logging(args)
        SharedState(None, None, '').signal_start().join(timeout=5)
        return parser.exit(0)

    if args.stop:
        setup_logging(args)
        SharedState(None, None, '').signal_stop().join(timeout=5)
        return parser.exit(0)

    if not args.json:
        return parser.exit(0, 'nothing to do')

    # noinspection PyBroadException
    try:
        dat = json.loads(args.json)
    except json.JSONDecodeError as exc:
        print("PARSE ERROR:\t\n\t", (args.json, exc))
        return parser.exit(1)

    send = PlaylistSender()
    time.sleep(1.0)

    # warm up the pub/sub to give subscribers the chance to connect. this utility is transient and
    # only used for debugging, so this problem doesnt manifest in long running applications
    for i in range(10):
        send.process()

    send.process(**dat)
    send.close(block=True)
    print("SENT: %r" % dat)
