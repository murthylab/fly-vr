import time
import uuid
import os.path
import collections
import multiprocessing

import yaml
import h5py
import numpy as np

from flyvr.common.concurrent_task import ConcurrentTask

from PIL import Image
from psychopy import visual, core, event
from psychopy.visual.windowwarp import Warper


class _Dottable(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


class VideoStimPlaylist(object):

    def __init__(self, *stims):
        self._stims = collections.OrderedDict()
        for s in stims:
            s.show = False
            self._stims[s.identifier] = s

    def initialize(self, win):
        [s.initialize(win) for s in self._stims.values()]

    def update_and_draw(self, *args, **kwargs):
        for s in self._stims.values():
            s.update_and_draw(*args, **kwargs)

    def describe(self):
        return [{id_: s.describe()} for id_, s in self._stims.items()]

    def update_params(self, identifier, **params):
        self._stims[identifier].update_params(**params)

    def play_item(self, identifier):
        for sid, s in self._stims.items():
            s.show = sid == identifier

    def play(self, stim):
        self._stims[stim.identifier] = stim


class VideoStim(object):
    NAME = 'grating'
    NUM_VIDEO_FIELDS = 7

    def __init__(self, **params):
        self._id = params.pop('identifier', uuid.uuid4().hex)

        self.p = _Dottable(params)
        self.show = params.pop('show', True)

    @property
    def identifier(self):
        return str(self._id)[:32]

    def initialize(self, win):
        raise NotImplementedError

    def update_and_draw(self, *args, **kwargs):
        if self.show:
            self.update(*args, **kwargs)
            self.draw()

    def update(self, win, logger, frame_num):
        raise NotImplementedError

    def draw(self):
        raise NotImplementedError

    def describe(self):
        d = {'name': self.NAME}
        d.update(self.p)
        return d

    def update_params(self, **params):
        # noinspection PyCallByClass
        dict.update(self.p, params)

    @classmethod
    def log_name(cls):
        return "/video/stimulus/{}".format(cls.NAME)

    @classmethod
    def create_log(cls, logger):
        logger.create(cls.log_name(),
                      shape=[2048, cls.NUM_VIDEO_FIELDS],
                      maxshape=[None, cls.NUM_VIDEO_FIELDS], dtype=np.float64,
                      chunks=(2048, cls.NUM_VIDEO_FIELDS))


class NoStim(VideoStim):
    NAME = 'none'
    NUM_VIDEO_FIELDS = 1

    def initialize(self, win):
        pass

    def update(self, win, logger, frame_num):
        logger.log(self.log_name(),
                   np.array([frame_num]))

    def draw(self):
        pass


# noinspection PyUnresolvedReferences
class GratingStim(VideoStim):
    NAME = 'grating'
    NUM_VIDEO_FIELDS = 7

    # for now fields are:
    # 0: frameNum
    # 1: background color: [-1, 1]
    # 2: object 1: 1 = grating, ...
    # 3: object 1: size
    # 4: object 1: phase
    # 5: object 1: color
    # 6: object 1: phase

    def __init__(self, sf=50, stim_size=5, stim_color=-1, bg_color=0.5, **kwargs):
        super().__init__(sf=int(sf),
                         stim_size=int(stim_size),
                         stim_color=int(stim_color),
                         bg_color=float(bg_color), **kwargs)
        self.screen = None

    def initialize(self, win):
        self.screen = visual.GratingStim(win=win, size=self.p.stim_size,
                                         pos=[0, 0], sf=self.p.sf,
                                         color=self.p.stim_color, phase=0)

    def update(self, win, logger, frame_num):
        self.screen.setPhase(0.05, '+')
        logger.log(self.log_name(),
                   np.array([frame_num,
                             self.p.bg_color,
                             1,
                             self.p.sf,
                             self.p.stim_size,
                             self.p.stim_color,
                             self.screen.phase[0]]))

    def draw(self):
        self.screen.draw()


class MovingSquareStim(VideoStim):
    NAME = 'moving_square'
    NUM_VIDEO_FIELDS = 7

    def __init__(self, size=(0.25, 0.25), speed=(0.01, 0), offset=(0.2, -0.5),
                 bg_color=-1, fg_color=1, **kwargs):
        super().__init__(size=[float(size[0]), float(size[1])],
                         speed=[float(speed[0]), float(speed[1])],
                         offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)
        self.screen = None

    def initialize(self, win):
        self.screen = visual.Rect(win=win,
                                  size=self.p.size, pos=self.p.offset,
                                  lineColor=None, fillColor=self.p.fg_color)

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        self.screen.pos += self.p.speed
        if self.screen.pos[0] >= 1:
            self.screen.pos[0] = -1
        if self.screen.pos[1] >= 1:
            self.screen.pos[1] = -1
            self.screen.pos[1] = -1

        logger.log(self.log_name(),
                   np.array([frame_num,
                             self.p.bg_color,
                             0,
                             self.screen.pos[0], self.screen.pos[1],
                             self.screen.size[0], self.screen.size[1]]))

    def draw(self):
        self.screen.draw()


class PipStim(VideoStim):
    NAME = 'pipstim'
    NUM_VIDEO_FIELDS = 7

    def __init__(self, filename='pipStim.mat', offset=(0.2, -0.5), bg_color=-1, fg_color=1, **kwargs):
        super().__init__(offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)

        with h5py.File(filename, 'r') as f:
            self._tdis = f['tDis'][:, 0]
            self._tang = f['tAng'][:, 0]

        self.screen = None

    def initialize(self, win):
        self.screen = visual.Rect(win=win,
                                  size=(0.25, 0.25), pos=self.p.offset,
                                  lineColor=None, fillColor=self.p.fg_color)

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        self.screen.pos = self._tang[round(frame_num)] / 180 + xoffset, yoffset
        self.screen.size = 1 / self._tdis[round(frame_num)], 1 / self._tdis[round(frame_num)]

        logger.log(self.log_name(),
                   np.array([frame_num,
                             self.p.bg_color,
                             0,
                             self.screen.pos[0], self.screen.pos[1],
                             self.screen.size[0], self.screen.size[1]]))

    def draw(self):
        self.screen.draw()


class LoomingStim(VideoStim):

    NAME = 'looming'
    NUM_VIDEO_FIELDS = 7

    def __init__(self, size_min=0.05, size_max=0.8, speed=0.01, offset=(0.2, -0.5),
                 bg_color=-1, fg_color=1, **kwargs):
        super().__init__(size_min=float(size_min), size_max=float(size_max), speed=float(speed),
                         offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)
        self.screen = None

    def initialize(self, win):
        self.screen = visual.Rect(win=win,
                                  size=self.p.size_min, pos=self.p.offset,
                                  lineColor=None, fillColor=self.p.fg_color)

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        self.screen.size += self.p.speed
        if self.screen.size[0] > self.p.size_max:
            self.screen.size = (self.p.size_min, self.p.size_min)

        logger.log(self.log_name(),
                   np.array([frame_num,
                             self.p.bg_color,
                             0,
                             self.screen.pos[0], self.screen.pos[1],
                             self.screen.size[0], self.screen.size[1]]))

    def draw(self):
        self.screen.draw()


class MayaModel(VideoStim):

    NAME = 'maya_model'
    NUM_VIDEO_FIELDS = 7

    def __init__(self, bg_color=(178 / 256) * 2 - 1, frame_start=10000, offset=(0.2, -0.5), **kwargs):
        super().__init__(bg_color=float(bg_color),
                         offset=[float(offset[0]), float(offset[1])], **kwargs)

        self._imgs = self.screen = None
        self._image_names = ['mayamodel/femalefly360deg/fly' + str(img_num) + '.png' for img_num in range(-179, 181)]

        angles = np.load('mayamodel/angles_fly19.npy')
        top_y = np.load('mayamodel/tops_fly19.npy')
        bottom_y = np.load('mayamodel/bottoms_fly19.npy')
        left_x = np.load('mayamodel/lefts_fly19.npy')
        right_x = np.load('mayamodel/rights_fly19.npy')

        self._angles = angles[frame_start:]
        self._img_pos = [(left_x[frame_start:] + right_x[frame_start:]) / 2,
                         (top_y[frame_start:] + bottom_y[frame_start:]) / 2]
        self._img_size = [right_x[frame_start:] - left_x[frame_start:],
                          top_y[frame_start:] - bottom_y[frame_start:]]

    def initialize(self, win):
        self._imgs = [visual.ImageStim(win=win, image=Image.open(i).convert('L')) for i in self._image_names]
        self.screen = self._imgs[0]

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        # right now moving at 30 Hz but projecting at 60 Hz
        self.screen = self._imgs[self._angles[round(frame_num / 2)]]
        self.screen.pos = [self._img_pos[0][round(frame_num / 2)] + xoffset,
                           self._img_pos[1][round(frame_num / 2)] + yoffset]
        self.screen.size = [self._img_size[0][round(frame_num / 2)],
                            self._img_size[1][round(frame_num / 2)]]

        logger.log(self.log_name(),
                   np.array([frame_num,
                             self.p.bg_color,
                             2,
                             self.screen.pos[0], self.screen.pos[1],
                             self.screen.size[0], self.screen.size[1]]))

    def draw(self):
        self.screen.draw()


class OptModel(VideoStim):

    NAME = 'opt_model'
    NUM_VIDEO_FIELDS = 7

    def __init__(self, bg_color=(178 / 256) * 2 - 1, offset=(0.2, -0.5), **kwargs):
        super().__init__(bg_color=float(bg_color),
                         offset=[float(offset[0]), float(offset[1])], **kwargs)

        self._imgs = self.screen = None

        self._image_names = ['mayamodel/femalefly360deg/fly' + str(i) + '.png' for i in range(-179, 181)]

        angles_v = np.load('mayamodel/forwardvelocity/angles_optstim.npy')

        ty_v = np.load('mayamodel/forwardvelocity/tops_optstim.npy')
        by_v = np.load('mayamodel/forwardvelocity/bottoms_optstim.npy')
        lx_v = np.load('mayamodel/forwardvelocity/lefts_optstim.npy')
        rx_v = np.load('mayamodel/forwardvelocity/rights_optstim.npy')

        angles_p = np.load('mayamodel/pulse/angles_optstim.npy')

        ty_p = np.load('mayamodel/pulse/tops_optstim.npy')
        by_p = np.load('mayamodel/pulse/bottoms_optstim.npy')
        lx_p = np.load('mayamodel/pulse/lefts_optstim.npy')
        rx_p = np.load('mayamodel/pulse/rights_optstim.npy')

        self._angles = angles_v[:300]
        self._angles = np.append(self._angles, angles_p[:300])
        self._img_pos = np.array([(lx_v[:300] + rx_v[:300]) / 2, (ty_v[:300] + by_v[:300]) / 2])
        self._img_pos = np.append(self._img_pos,
                                  np.array([(lx_p[:300] + rx_p[:300]) / 2, (ty_p[:300] + by_p[:300]) / 2]),
                                  axis=1)

        self._img_size = [rx_v[:300] - lx_v[:300], ty_v[:300] - by_v[:300]]
        self._img_size = np.append(self._img_size, np.array([rx_p[:300] - lx_p[:300], ty_p[:300] - by_p[:300]]),
                                   axis=1)

        for ii in range(300, 3300, 300):
            self._angles = np.append(self._angles, angles_v[ii:ii + 300])
            self._angles = np.append(self._angles, angles_p[ii:ii + 300])

            self._img_pos = np.append(self._img_pos, np.array(
                [(lx_v[ii:ii + 300] + rx_v[ii:ii + 300]) / 2, (ty_v[ii:ii + 300] + by_v[ii:ii + 300]) / 2]),
                                     axis=1)
            self._img_pos = np.append(self._img_pos, np.array(
                [(lx_p[ii:ii + 300] + rx_p[ii:ii + 300]) / 2, (ty_p[ii:ii + 300] + by_p[ii:ii + 300]) / 2]),
                                     axis=1)

            self._img_size = np.append(self._img_size, np.array(
                [rx_v[ii:ii + 300] - lx_v[ii:ii + 300], ty_v[ii:ii + 300] - by_v[ii:ii + 300]]), axis=1)
            self._img_size = np.append(self._img_size, np.array(
                [rx_p[ii:ii + 300] - lx_p[ii:ii + 300], ty_p[ii:ii + 300] - by_p[ii:ii + 300]]), axis=1)

    def initialize(self, win):
        self._imgs = [visual.ImageStim(win=win, image=Image.open(i).convert('L')) for i in self._image_names]
        self.screen = self._imgs[0]

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        # right now moving at 30 Hz but projecting at 60 Hz
        self.screen = self._imgs[self._angles[round(frame_num / 2)]]
        self.screen.pos = [self._img_pos[0][round(frame_num / 2)] + xoffset,
                           self._img_pos[1][round(frame_num / 2)] + yoffset]
        self.screen.size = [self._img_size[0][round(frame_num / 2)],
                            self._img_size[1][round(frame_num / 2)]]

        logger.log(self.log_name(),
                   np.array([frame_num,
                             self.p.bg_color,
                             2,
                             self.screen.pos[0], self.screen.pos[1],
                             self.screen.size[0], self.screen.size[1]]))

    def draw(self):
        self.screen.draw()


STIMS = (NoStim, GratingStim, MovingSquareStim, LoomingStim, MayaModel, OptModel, PipStim)


def stimulus_factory(name, **params):
    for s in STIMS:
        if name == s.NAME:
            return s(**params)
    raise ValueError("VideoStimulus '%s' not found" % name)


class VideoServer(object):

    def __init__(self, stim=None, shared_state=None, calibration_file=None):
        self._initial_stim = stim
        self.stim = self.mywin = self.synchRect = None

        self.samples_played = self.sync_signal = 0
        self.calibration_file = calibration_file

        # We will update variables related to audio playback in flyvr's shared state data if provided
        self.flyvr_shared_state = shared_state
        self.logger = shared_state.logger

        # Setup a stream end event, this is how the control will signal to the main thread when it exits.
        self.stream_end_event = multiprocessing.Event()

        # The process we will spawn the video server thread in.
        self.task = ConcurrentTask(task=self._video_server_main, comms='pipe')

        self.logger.create("/video/daq_synchronization_info", shape=[1024, 2], maxshape=[None, 2],
                           dtype=np.int64,
                           chunks=(1024, 2))
        for stimcls in STIMS:
            stimcls.create_log(self.logger)

    # This is how many records of calls to the callback function we store in memory.
    CALLBACK_TIMING_LOG_SIZE = 10000

    def _play(self, stim):
        print("Playing: %r" % stim)
        if isinstance(stim, (VideoStim, VideoStimPlaylist)):
            assert self.mywin
            stim.initialize(self.mywin)
            self.stim = stim
        elif isinstance(stim, str):
            self.stim.play_item(stim)

    def start_stream(self):
        self.task.start()
        return VideoStreamProxy(self)

    def _video_server_main(self, msg_receiver):
        """
        The main process function for the video server. Handles actually setting up the videodevice object\stream.
        Waits to receive objects to play on the stream, sent from other processes using a Queue or Pipe.

        :return: None
        """

        self.mywin = visual.Window([608, 684], monitor='DLP', screen=1, useFBO=True, color=0)

        self.synchRect = visual.Rect(win=self.mywin, size=(0.25, 0.25), pos=[0.75, -0.75],
                                     lineColor=None, fillColor='grey')

        if self.calibration_file is not None:
            warpfile = self.calibration_file
        else:
            warpfile = 'calibratedBallImage.data'

        if os.path.isfile(warpfile):
            # warp the image according to some calibration that we have already performed
            self.warper = Warper(self.mywin,
                                 # warp='spherical',
                                 warp='warpfile',
                                 warpfile="calibratedBallImage.data",
                                 warpGridsize=300,
                                 eyepoint=[0.5, 0.5],
                                 flipHorizontal=False,
                                 flipVertical=False)
        else:
            self.warper = Warper(self.mywin,
                                 warp='spherical',
                                 warpGridsize=300,
                                 eyepoint=[0.5, 0.5],
                                 flipHorizontal=False,
                                 flipVertical=False)

        if self._initial_stim is not None:
            self._play(self._initial_stim)

        while (not (self.stream_end_event.is_set() and self.flyvr_shared_state is not None and \
                    (self.flyvr_shared_state.is_running_well()))) and \
                (not (self.stream_end_event.is_set())):

            if msg_receiver.poll():
                msg = msg_receiver.recv()
                if isinstance(msg, (VideoStim, VideoStimPlaylist, str)):
                    self._play(msg)
                else:
                    raise NotImplementedError

            if self.stim is not None:
                self.stim.update_and_draw(self.mywin, self.logger, frame_num=self.samples_played)

                if self.sync_signal > 60 * 10:
                    self.synchRect.fillColor = 'black'
                    self.synch_signal = 0
                elif self.sync_signal > 60 * 5:
                    self.synchRect.fillColor = 'white'

                self.synchRect.draw()
                self.mywin.flip()

                self.samples_played += 1
                self.sync_signal += 1

    def _stream_end(self):
        """
        Invoked at the end of stream playback by sounddevice. We can do any cleanup we need here.
        """

        # Trigger the event that marks a stream end, the main loop thread is waiting on this.
        self.stream_end_event.set()


class VideoStreamProxy:
    """
    The VideoStreamProxy class acts as an interface to a SoundServer object that is running on another process. It
    handles sending commands to the object on the other process.
    """

    def __init__(self, video_server):
        """
        Initialize the SoundStreamProxy with an already setup SoundServer object. This assummes that the server is
        running and ready to receive commands.

        :param sound_server: The SoundServer object to issue commands to.
        """
        self.video_server = video_server
        self.task = self.video_server.task

    def play(self, stim):
        """
        Send audio stimulus to the sound server for immediate playback.

        :param stim: The AudioStim object to play.
        :return: None
        """
        self.task.send(stim)

    def silence(self):
        """
        Set current playback to silence immediately.

        :return: None
        """
        self.play(None)

    def close(self):
        """
        Signal to the server to shutdown the stream.

        :return: None
        """
        self.video_server.stream_end_event.set()

        # We send the server a junk signal. This will cause the message loop to wake up, skip the message because its
        # junk, and check whether to exit, which it will see is set and will close the stream. Little bit of a hack but
        # it gets the job done I guess.
        self.play("KILL")

        # Wait till the server goes away.
        while self.task.is_alive():
            time.sleep(0.1)


def _build_playlist(yaml_path):
    stims = []

    with open(yaml_path, 'rt') as f:
        dat = yaml.load(f)
        try:
            for item_def in dat['playlist']['video']:
                id_, defn = item_def.popitem()
                stims.append(stimulus_factory(defn.pop('name'), identifier=id_, **defn))
        except KeyError:
            pass

    return VideoStimPlaylist(*stims)


def run_video_server(options):
    from flyvr.common import SharedState
    from flyvr.common.logger import DatasetLogServerThreaded
    from flyvr.common.ipc import PlaylistReciever

    pr = PlaylistReciever()

    playlist_stim = None
    if options.stim_playlist:
        playlist_stim = _build_playlist(options.stim_playlist)

    with DatasetLogServerThreaded() as log_server:
        logger = log_server.start_logging_server(options.record_file.replace('.h5', '.video_server.h5'))
        state = SharedState(options=options, logger=logger)

        if options.visual_stimulus:
            stim = stimulus_factory(options.visual_stimulus)
        else:
            stim = None

        video_server = VideoServer(stim=stim,
                                   calibration_file=options.screen_calibration,
                                   shared_state=state)
        video_client = video_server.start_stream()

        if playlist_stim is not None:
            video_client.play(playlist_stim)

        print('Waiting For Video')
        time.sleep(10)  # takes a bit for the video_server thread to create the psychopy window

        while True:
            elem = pr.get_next_element()
            if elem:
                try:
                    if 'video' in elem:
                        defn = elem['video']
                        stim = stimulus_factory(defn['name'], **defn.get('configuration', {}))
                        video_client.play(stim)
                    elif 'video_item' in elem:
                        video_client.play(elem['video_item']['identifier'])
                    else:
                        print("Ignoring Message")
                except Exception as exc:
                    print("-------", exc)


def main_video_server():
    import sys
    from flyvr.common.build_arg_parser import parse_arguments

    try:
        options = parse_arguments()
    except ValueError as ex:
        sys.stderr.write("Invalid Config Error: \n" + str(ex) + "\n")
        sys.exit(-1)

    run_video_server(options)
