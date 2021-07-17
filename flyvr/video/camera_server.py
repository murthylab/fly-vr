import time
import logging
import threading

import cv2
import numpy as np

try:
    import PySpin
    _PYSPIN_ERROR = None
except ImportError:
    PySpin = None
    _PYSPIN_ERROR = 'PySpin not installed'
except Exception as _e:
    PySpin = None
    _PYSPIN_ERROR = 'PySpin error: %s' % _e

from imageio_ffmpeg import write_frames, get_ffmpeg_exe, get_ffmpeg_version

from flyvr.common import SharedState, BACKEND_CAMERA
from flyvr.common.build_arg_parser import setup_logging
from flyvr.common.ipc import PlaylistReciever, CommonMessages


class _FakeCamera(object):

    def __init__(self):
        self._i = 0

    def __repr__(self):
        return 'FAKE'

    def next_frame(self):
        self._i += 1
        bw = self.encode_image(self._i)
        return self._i - 0, cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

    def start(self, **camera_options):
        pass

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


class _CameraProperties(dict):

    _PROPS = {'Width': int,
              'Height': int,
              'SensorWidth': int,
              'SensorHeight': int,
              'OffsetX': int,
              'OffsetY': int,
              'ExposureTime': float,
              'Gain': float,
              'Gamma': float,
              'GammaEnable': bool,
              'AcquisitionStart': bool,
              'AcquisitionStop': bool,
              'AcquisitionFrameCount': int,
              'AcquisitionMode': str,
              'AcquisitionFrameRateEnable': bool,
              'AcquisitionFrameRateEnabled': bool,
              'AcquisitionFrameRate': float,
              'AcquisitionFrameRateAuto': str,  # special handling
              'DeviceTemperature': float,
              'TriggerMode': str,
              'TriggerSource': str,
              'LineSelector': str,
              'TriggerSelector': str,
              'LineMode': str,
              'LineSource': str,
              'BlackLevel': float,
              'TriggerOverlap': str,
              'TriggerDelay': float,
              'ReverseX': bool,
              'ReverseY': bool,
              'V3_3Enable': bool,
              'UserOutputValue': bool,
              'AcquisitionResultingFrameRate': float,
              }

    _NOT_IMPLEMENTED = {'CenterX', 'CenterY'}

    def __init__(self, cam):
        self._cam = cam
        self._log = logging.getLogger('flyvr.camera.properties')
        dict.__init__(self)

    def __setitem__(self, key, val):
        ok = True
        if key == 'ExposureAuto':
            if self._cam.ExposureAuto.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                if val == 'Off':
                    self._cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                else:
                    self._cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Continuous)
        elif key == 'GainAuto':
            if self._cam.GainAuto.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                if val == 'Off':
                    self._cam.GainAuto.SetValue(PySpin.GainAuto_Off)
                else:
                    self._cam.GainAuto.SetValue(PySpin.GainAuto_Continuous)
        elif key == 'BalanceWhiteAuto':
            if self._cam.BalanceWhiteAuto.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                if val == 'Off':
                    self._cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Off)
                else:
                    self._cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Continuous)
        elif key == 'DeviceLinkThroughputLimitMode':
            if self._cam.DeviceLinkThroughputLimitMode.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                if val == 'Off':
                    self._cam.DeviceLinkThroughputLimitMode.SetValue(PySpin.DeviceLinkThroughputLimitMode_Off)
                else:
                    self._cam.DeviceLinkThroughputLimitMode.SetValue(PySpin.DeviceLinkThroughputLimitMode_On)
        elif key == 'TriggerMode':
            if self._cam.TriggerMode.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                if val == 'Off':
                    self._cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
                else:
                    self._cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
        elif key == 'TriggerSource':
            if self._cam.TriggerSource.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'TriggerSource_%s' % val)
                self._cam.TriggerSource.SetValue(v)
        elif key == 'LineSelector':
            if self._cam.LineSelector.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'LineSelector_%s' % val)
                self._cam.LineSelector.SetValue(v)
        elif key == 'TriggerSelector':
            if self._cam.TriggerSelector.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'TriggerSelector_%s' % val)
                self._cam.TriggerSelector.SetValue(v)
        elif key == 'LineMode':
            if self._cam.LineMode.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'LineMode_%s' % val)
                self._cam.LineMode.SetValue(v)
        elif key == 'AcquisitionMode':
            if self._cam.AcquisitionMode.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'AcquisitionMode_%s' % val)
                self._cam.AcquisitionMode.SetValue(v)
        elif key == 'LineSource':
            if self._cam.LineSource.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'LineSource_%s' % val)
                self._cam.LineSource.SetValue(v)
        elif key == 'TriggerOverlap':
            if self._cam.TriggerOverlap.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'TriggerOverlap_%s' % val)
                self._cam.TriggerOverlap.SetValue(v)
        elif key == 'AcquisitionFrameRateAuto':
            if str(val) == 'Off':
                nm = self._cam.GetNodeMap()
                # fixme: I can't work out how to get the enum names/values, but 0 is *always* Off
                # 'Continuous' = 2
                PySpin.CEnumerationPtr(nm.GetNode('AcquisitionFrameRateAuto')).SetIntValue(0)
                del nm
                ok = True
        elif key in {'AcquisitionStart', 'AcquisitionStop'}:
            p = getattr(self._cam, key)
            if p.GetAccessMode() not in (PySpin.RW, PySpin.WO):
                self._log.error('%s is not writable (mode: %x)' % (key, p.GetAccessMode()))
                ok = False
            else:
                p.Execute()
        elif key in self._NOT_IMPLEMENTED:
            pass
        elif key == 'AcquisitionFrameRateEnabled':
            nm = self._cam.GetNodeMap()
            ack_enabled = PySpin.CBooleanPtr(nm.GetNode("AcquisitionFrameRateEnabled"))
            if PySpin.IsAvailable(ack_enabled) and PySpin.IsWritable(ack_enabled):
                v = True if ((val is True) or (str(val) in ('On', 'on', 'true', 'True'))) else False
                ack_enabled.SetValue(v)
                # we can't actually know if this succeeds other than if it's caught or not
            else:
                self._log.error('AcquisitionFrameRateEnabled is not available or writable')
                ok = False
        elif key == 'PixelFormat':
            if self._cam.PixelFormat.GetAccessMode() != PySpin.RW:
                ok = False
            else:
                v = getattr(PySpin, 'PixelFormat_%s' % val, None)
                if v is None:
                    raise RuntimeError('PixelFormat=%s is invalid' % val)
                self._cam.PixelFormat.SetValue(v)
        elif key in self._PROPS:
            try:
                p = getattr(self._cam, key)
                if p.GetAccessMode() not in (PySpin.RW, PySpin.WO):
                    self._log.error('%s is not writable (mode: %x)' % (key, p.GetAccessMode()))
                    ok = False
                else:
                    p.SetValue(self._PROPS[key](val))
            except PySpin.SpinnakerException as exc:
                if 'OutOfRangeException' in str(exc):
                    self._log.warn('could not set attribute: %s (%s)' % (key, exc))
                else:
                    self._log.error('could not set attribute: %s (%s)' % (key, exc))
            except AttributeError as exc:
                self._log.error('could not set attribute (not supported?): %s (%s)' % (key, exc))
        else:
            ok = False

        self._log.debug('set ok:%s %s=%s' % (ok, key, val))

        if not ok:
            raise RuntimeError(key)

    def __getitem__(self, item):
        if item != 'DeviceTemperature':
            self._log.debug('get %s' % item)

        if item == 'ExposureTimeRaw':
            raise KeyError(item)
        elif item == 'PixelColorFilter':
            # noinspection PyBroadException
            try:
                v = self._cam.PixelFormat.ToString()
                if v == 'BayerRG8':
                    return 'BayerRG'
                elif v == 'Mono8':
                    return ''
                else:
                    self._log.error('unknown / unsupported spinnaker PixelFormat: %s' % v)
                    v = ''
            except Exception:
                self._log.warn('could not read camera PixelFormat', exc_info=True)
                v = ''
            return v
        elif item in self._PROPS:
            try:
                p = getattr(self._cam, item)
                if p.GetAccessMode() == PySpin.RO or p.GetAccessMode() == PySpin.RW:
                    return p.GetValue()
            except (AttributeError, PySpin.SpinnakerException) as exc:
                self._log.error('could not read attribute: %s (%s)' % (item, exc))
                raise KeyError(item)
        else:
            return dict.__getitem__(self, item)

    @staticmethod
    def spinnaker_node_cmd(cam, cam_node_str, cam_method_str, cam_node_arg=None, pyspin_mode_str=None, log=None):
        """ Performs method on input cam node with optional access mode check """

        info_str = 'camera ' + cam.GetUniqueID() + ' - executing: "' + '.'.join([cam_node_str, cam_method_str]) + '('
        if cam_node_arg is not None:
            info_str += str(cam_node_arg)
        info_str += ')"'

        if log is not None:
            log.debug(info_str)

        cam_node = cam
        cam_node_str_split = cam_node_str.split('.')
        for sub_cam_node_str in cam_node_str_split:
            cam_node = getattr(cam_node, sub_cam_node_str)

        # Perform optional access mode check
        if pyspin_mode_str is not None:
            if cam_node.GetAccessMode() != getattr(PySpin, pyspin_mode_str):
                raise RuntimeError('Access mode check failed for: "' + cam_node_str + '" with mode: "' +
                                   pyspin_mode_str + '".')

        # Format command argument in case it's a string containing a PySpin attribute
        if isinstance(cam_node_arg, str):
            cam_node_arg_split = cam_node_arg.split('.')
            if cam_node_arg_split[0] == 'PySpin':
                if len(cam_node_arg_split) == 2:
                    cam_node_arg = getattr(PySpin, cam_node_arg_split[1])
                else:
                    raise RuntimeError('Arguments containing nested PySpin attributes are currently not supported...')

        # Perform command
        if cam_node_arg is None:
            return getattr(cam_node, cam_method_str)()
        else:
            return getattr(cam_node, cam_method_str)(cam_node_arg)

    def get_value_string(self, item):
        # performs the necessary error checking
        if self[item] is not None:
            return getattr(self._cam, item).ToString()

    def get_value_range(self, what):
        r = 0, 0
        if what in self._PROPS:
            try:
                p = getattr(self._cam, what)
                r = p.GetMin(), p.GetMax()
            except (AttributeError, PySpin.SpinnakerException) as exc:
                self._log.error('could not read attribute range: %s (%s)' % (what, exc))

        self._log.debug('range %s = %r' % (what, r))
        return r


class _GrabError(Exception):
    pass


class _GrabTimeout(Exception):
    pass


class _InitError(Exception):
    pass


class _Camera(object):

    def __init__(self, cam):
        self._i = 0
        self._t0 = self._t1 = None

        self._log = logging.getLogger('flyvr.camera')

        self._cam = cam
        try:
            self._cam.Init()
        except Exception:
            raise _InitError()

        self.sn, self.camera_name = self.camera_info(cam.GetTLDeviceNodeMap())
        self.properties = _CameraProperties(cam)

    def __repr__(self):
        return str(self.camera_name)

    def next_frame(self, **kwargs):
        self._i += 1

        timeout = kwargs.get('timeout', PySpin.EVENT_TIMEOUT_INFINITE)

        try:
            image_result = self._cam.GetNextImage(timeout)
        except PySpin.SpinnakerException:
            # timeout was set by user
            if timeout != PySpin.EVENT_TIMEOUT_INFINITE:
                raise _GrabTimeout('%sms' % timeout)
            else:
                raise

        if image_result.IsIncomplete():
            raise _GrabError('Image incomplete with image status %d ...' % image_result.GetImageStatus())

        frame = image_result.GetNDArray()
        fn = image_result.GetFrameID()
        ts = image_result.GetTimeStamp() / 1e9
        image_result.Release()

        self._t1 = self._t1 or ts
        t = ts - self._t1 + self._t0

        return fn, frame

    def _node_cmd(self, cam_node_str, cam_method_str, cam_node_arg=None, pyspin_mode_str=None):
        """ Performs method on input cam node with optional access mode check """
        _CameraProperties.spinnaker_node_cmd(self._cam,
                                             cam_node_str=cam_node_str,
                                             cam_method_str=cam_method_str,
                                             cam_node_arg=cam_node_arg,
                                             pyspin_mode_str=pyspin_mode_str,
                                             log=self._log)

    def start(self, **camera_options):
        self._cam.BeginAcquisition()
        self._t0 = time.time()

        self._node_cmd('AcquisitionStop', 'Execute', None, None)
        self._node_cmd('PixelFormat', 'SetValue', 'PySpin.PixelFormat_Mono8', None)

        reset = camera_options.pop('ResetFactoryDefaults', False)
        if reset:
            self._node_cmd('UserSetSelector', 'SetValue', 'PySpin.UserSetDefault_Default', None)
            self._node_cmd('UserSetLoad', 'Execute', None, None)

        for k, v in camera_options.items():
            self._log.info("set %s='%s'" % (k, v))
            # noinspection PyBroadException
            try:
                self.properties[k] = v
            except Exception:
                self._log.error("error setting property '%s'" % k, exc_info=True)

    def close(self):
        self._cam.DeInit()
        self.properties._cam = None
        del self._cam
        self._cam = None
        self._log.debug('closed camera')

    @property
    def image_size(self):
        h, w = int(self.properties['Height']), int(self.properties['Width'])
        return w, h

    @staticmethod
    def camera_info(nodemap_tldevice):
        device_serial_number = device_vendor_name = device_model_name = None

        node_device_serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
        if PySpin.IsAvailable(node_device_serial_number) and PySpin.IsReadable(node_device_serial_number):
            device_serial_number = node_device_serial_number.GetValue()

        node_device_vendor_name = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceVendorName'))
        if PySpin.IsAvailable(node_device_vendor_name) and PySpin.IsReadable(node_device_vendor_name):
            device_vendor_name = node_device_vendor_name.ToString()

        node_device_model_name = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName'))
        if PySpin.IsAvailable(node_device_model_name) and PySpin.IsReadable(node_device_model_name):
            device_model_name = node_device_model_name.ToString()

        friendly_name = '%s %s (%s)' % (device_vendor_name, device_model_name, device_serial_number)
        serial_number = str(device_serial_number)

        return serial_number, friendly_name


def run_camera_server(options, evt=None):
    from flyvr.common import SharedState, Randomizer
    from flyvr.common.logger import DatasetLogServerThreaded

    setup_logging(options)

    log = logging.getLogger('flyvr.camera.main')
    log.info('FFMPEG Version %s' % get_ffmpeg_version())

    system = None

    if options.camera_serial == 'FAKE':
        cam = _FakeCamera()
        log.info('Fake camera selected')
    elif options.camera_serial:

        if PySpin is None:
            log.fatal('PySpin not installed')
            cam = _FakeCamera()

        else:
            system = PySpin.System.GetInstance()

            sn = str(options.camera_serial)
            cam_list = system.GetCameras()
            try:
                c = cam_list.GetBySerialNumber(sn)
            except AttributeError:
                log.info('spinnaker API misses GetBySerialNumber')
                c = cam_list.GetBySerial(sn)

            try:
                cam = _Camera(c)
            except _InitError:
                cam = _FakeCamera()
                log.fatal("camera with serial number '%s' not found" % sn)

        log.info('Camera: %r' % cam)
    else:
        log.info('Camera not selected')
        return

    log.info('starting camera')
    cam.start()

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

            if options.camera_show and ((int(fn) % options.camera_show) == 0):
                cv2.imshow(repr(cam), img)
                cv2.waitKey(1)

        writer.close()

    cam.close()

    if system is not None:
        log.info('closing system instance')
        try:
            system.ReleaseInstance()
        except KeyboardInterrupt:
            pass


def main_camera_server():
    from zmq.utils.win32 import allow_interrupt
    from flyvr.common.build_arg_parser import build_argparser, parse_options

    parser = build_argparser()
    parser.add_argument('--print-devices', action='store_true', help='list attached camera serial numbers')
    options = parse_options(parser.parse_args(), parser)

    if options.print_devices:
        if PySpin is None:
            parser.error(_PYSPIN_ERROR)

        print('Cameras:')

        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        for cam in cam_list:
            nm = cam.GetTLDeviceNodeMap()
            _, desc = _Camera.camera_info(nm)
            print('\t%s' % desc)
            del nm

        cam_list.Clear()
        del cam_list

        system.ReleaseInstance()
        parser.exit(0)

    quit_evt = threading.Event()

    # noinspection PyUnusedLocal
    def ctrlc(*args):
        quit_evt.set()

    with allow_interrupt(action=ctrlc):
        run_camera_server(options, quit_evt)
