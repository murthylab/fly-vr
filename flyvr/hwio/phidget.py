import time
import threading
import logging

from Phidget22.Net import Net
from Phidget22.Devices.DigitalOutput import DigitalOutput

from flyvr.common.ipc import Reciever, RELAY_RECIEVE_PORT, RELAY_HOST, CommonMessages

DEFAULT_REMOTE = '127.0.0.1', 5661


class PhidgetIO(object):

    def __init__(self, tp_start, tp_stop, tp_next, tp_enable, debug_led=None, remote_details=None):
        self._log = logging.getLogger('flyvr.hwio.PhidgetIO')

        if remote_details:
            host, port = remote_details
            Net.addServer('localhost', host, port, '', 0)
            self._log.info('connecting to remote phidget: %r' % (remote_details, ))

        self._stack = 0

        self._tp_enable = tp_enable
        self._tp_start = self._tp_stop = self._tp_next = None
        if tp_enable:
            self._tp_start = DigitalOutput()
            self._tp_start.setIsHubPortDevice(True)
            self._tp_start.setHubPort(tp_start)
            self._tp_start.setIsRemote(True if remote_details else False)

            self._tp_stop = DigitalOutput()
            self._tp_stop.setIsHubPortDevice(True)
            self._tp_stop.setHubPort(tp_stop)
            self._tp_stop.setIsRemote(True if remote_details else False)

            self._tp_next = DigitalOutput()
            self._tp_next.setIsHubPortDevice(True)
            self._tp_next.setHubPort(tp_next)
            self._tp_next.setIsRemote(True if remote_details else False)

            self._log.info('2P scanimage connections: start=%s stop=%s next=%s' % (tp_start, tp_stop, tp_next))
        else:
            self._log.info('2P scanimage disabled')

        self._led = 0
        self._tp_led = None
        if debug_led is not None:
            self._tp_led = DigitalOutput()
            self._tp_led.setIsHubPortDevice(True)
            self._tp_led.setHubPort(debug_led)
            self._tp_led.setIsRemote(True if remote_details else False)
            self._log.info('debug led=%s' % debug_led)

        for tp in (self._tp_start, self._tp_stop, self._tp_next, self._tp_led):
            if tp is not None:
                tp.openWaitForAttachment(20000 if remote_details else 5000)

        if self._tp_led is not None:
            for _ in range(6):
                self._flash_led()
                time.sleep(0.1)

        self._rx = Reciever(host=RELAY_HOST, port=RELAY_RECIEVE_PORT, channel=b'')

    def close(self):
        for tp in (self._tp_start, self._tp_stop, self._tp_next, self._tp_led):
            if tp is not None:
                tp.close()

    def _flash_led(self):
        if self._tp_led is not None:
            self._led ^= 1
            self._tp_led.setDutyCycle(self._led)

    def next_image(self):
        # pulse both start and next hight
        self._tp_start.setDutyCycle(1)
        if self._stack > 0:
            self._tp_next.setDutyCycle(1)

        time.sleep(0.001)

        self._tp_start.setDutyCycle(0)
        if self._stack > 0:
            self._tp_next.setDutyCycle(0)

        self._log.info('starting new scanimage file: %d' % self._stack)
        self._stack += 1

    def run(self):
        while True:
            msg = self._rx.get_next_element()
            if msg and (CommonMessages.EXPERIMENT_PLAYLIST_ITEM in msg):

                # a backend is playing a new playlist item
                self._flash_led()

                if self._tp_enable:
                    self.next_image()

            print(msg)


def run_phidget_io(options):
    from flyvr.common.build_arg_parser import setup_logging

    setup_logging(options)

    io = PhidgetIO(tp_start=options.remote_start_2P_channel,
                   tp_stop=options.remote_stop_2P_channel,
                   tp_next=options.remote_next_2P_channel,
                   tp_enable=options.remote_2P_enable,
                   debug_led=options.debug_led,
                   remote_details=DEFAULT_REMOTE if options.network else None)
    io.run()


def main_phidget():
    import threading

    from zmq.utils.win32 import allow_interrupt
    from flyvr.common.build_arg_parser import build_argparser, parse_options

    parser = build_argparser()
    parser.add_argument("--debug_led",
                        type=int,
                        help="flash this LED upon IPC messages (should not be 3,4,5)",
                        default=None)
    parser.add_argument("--network",
                        action='store_true',
                        help='connect to phidget over network protocol',
                        default=False)

    options = parse_options(parser.parse_args(), parser)

    # silly little dance to make ZMQ blocking read ctrl-c killable by running the entire
    # thing in a thread and waiting on an event instead

    quit_evt = threading.Event()

    def ctrlc(*args):
        quit_evt.set()

    t = threading.Thread(target=run_phidget_io, args=(options, ), daemon=True)
    t.start()

    with allow_interrupt(action=ctrlc):

        try:
            quit_evt.wait()
        except KeyboardInterrupt:
            pass
