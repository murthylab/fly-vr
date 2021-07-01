import logging
import threading

import cv2
import numpy as np

from imageio_ffmpeg import write_frames, get_ffmpeg_exe, get_ffmpeg_version

from flyvr.common import SharedState, BACKEND_CAMERA
from flyvr.common.build_arg_parser import setup_logging
from flyvr.common.ipc import PlaylistReciever, CommonMessages


class _FakeCamera(object):

    def __init__(self):
        self._i = 0

    def next_frame(self):
        self._i += 1
        bw = self.encode_image(self._i)
        return self._i - 0, cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

    def close(self):
        pass

    @property
    def image_size(self):
        return 512, 512

    @staticmethod
    def encode_image(num, nbits=16, imgsize=512):
        row = np.fromiter((255 * int(c) for c in ('{0:0%db}' % nbits).format(num)), dtype=np.uint8)
        mat = np.tile(row, (nbits, 1))
        return cv2.resize(mat, dsize=(imgsize, imgsize), interpolation=cv2.INTER_NEAREST)

    @staticmethod
    def decode_image(img, nbits=16, imgsize=512):
        h, w = img.shape[:2]
        assert (h == imgsize) and (w == imgsize)
        assert len(img.shape) == 2
        img = cv2.resize(img, dsize=(nbits, nbits), interpolation=cv2.INTER_NEAREST)
        row = (np.mean(img, axis=0) > 127).astype(np.uint8)
        bstr = ''.join(str(v) for v in row)
        return int(bstr, 2)


class _Camera(object):

    def __init__(self, sn):
        self._i = 0
        self._sn = sn

    def next_frame(self):
        self._i += 1
        return self._i - 0, np.zeros((480, 640, 3), dtype=np.uint8)

    def close(self):
        pass

    @property
    def image_size(self):
        return 640, 480


def run_camera_server(options, evt=None):
    from flyvr.common import SharedState, Randomizer
    from flyvr.common.logger import DatasetLogServerThreaded

    setup_logging(options)

    log = logging.getLogger('flyvr.camera.main')
    log.info('FFMPEG Version %s' % get_ffmpeg_version())

    if options.camera_serial == 'FAKE':
        cam = _FakeCamera()
        log.info('Fake camera selected')
    elif options.camera_serial:
        cam = _Camera(options.camera_serial)
        log.info('Camera serial number: %s' % options.camera_serial)
    else:
        log.info('Camera not selected')
        return

    with DatasetLogServerThreaded() as log_server:
        logger = log_server.start_logging_server(options.record_file.replace('.h5', '.camera.h5'))
        state = SharedState(options=options, logger=logger, _quit_evt=evt)

        state.signal_ready(BACKEND_CAMERA)

        writer = write_frames(options.record_file.replace('.h5', '.camera.mp4'),
                              cam.image_size)
        writer.send(None)

        while True:
            fn, img = cam.next_frame()
            writer.send(img)

            if state.is_stopped():
                break

        writer.close()

    cam.close()


def main_camera_server():
    from zmq.utils.win32 import allow_interrupt
    from flyvr.common.build_arg_parser import build_argparser, parse_options

    parser = build_argparser()
    options = parse_options(parser.parse_args(), parser)

    quit_evt = threading.Event()

    # noinspection PyUnusedLocal
    def ctrlc(*args):
        quit_evt.set()

    with allow_interrupt(action=ctrlc):
        run_camera_server(options, quit_evt)
