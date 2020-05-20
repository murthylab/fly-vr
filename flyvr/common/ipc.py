import json
import pickle
import threading

import zmq


class _ZMQMultipartSender(object):
    def __init__(self, host, port, channel):
        ctx = zmq.Context()

        # fixme: IPC will be supported on windows beginning with next zmq release
        stream_address = "tcp://%s:%d" % (host, port)

        sock = ctx.socket(zmq.PUB)
        sock.bind(stream_address)
        self._channel = channel
        self._stream = sock

    def _send(self, data):
        self._stream.send_multipart((self._channel, data), zmq.NOBLOCK)


class PlaylistSender(_ZMQMultipartSender):

    HOST = '127.0.0.1'
    PORT = 6444
    PUB_CHANNEL = b'p'

    def __init__(self):
        super().__init__(self.HOST, self.PORT, self.PUB_CHANNEL)

    def process(self, **data):
        self._send(memoryview(pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)))

    def close(self, block=True):
        self._stream.close(linger=-1 if block else 0)


class PlaylistReciever(object):

    def __init__(self, host=PlaylistSender.HOST, port=PlaylistSender.PORT, channel=PlaylistSender.PUB_CHANNEL):
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


class PlaylistMirror(threading.Thread):

    daemon = True

    def __init__(self):
        threading.Thread.__init__(self)
        self._lock = threading.Lock()
        self._state = {}
        self._streamer = PlaylistReciever()

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


def main_ipc_send():
    import sys
    import json
    import time

    # noinspection PyBroadException
    try:
        dat = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        print("PARSE ERROR:\t\n\t", (sys.argv[1], exc))
        sys.exit(1)

    send = PlaylistSender()
    time.sleep(1.0)

    # warm up the pub/sub to give subscribers the chance to connect. this utility is transient and
    # only used for debugging, so this problem doesnt manifest in long running applications
    for i in range(10):
        send.process()

    # flyvr-ipc-send.exe "{\"audio_legacy\": \"sin\t10\t1\t0\t0\t0\t1\t650\"}"
    # flyvr-ipc-send.exe "{\"video\": {\"name\": \"looming\"}}"

    send.process(**dat)
    send.close(block=True)
    print("SENT: %r" % dat)
