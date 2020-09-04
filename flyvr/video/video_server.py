import uuid
import queue
import os.path
import logging
import threading
import collections

import h5py
import numpy as np

from flyvr.common import Dottable, Randomizer
from flyvr.common.build_arg_parser import setup_logging
from flyvr.projector.dlplc_tcp import LightCrafterTCP
from flyvr.common.ipc import PlaylistReciever

from PIL import Image
from psychopy import visual, core, event
from psychopy.visual.windowwarp import Warper
from psychopy.visual.windowframepack import ProjectorFramePacker


dlp_screen = [684, 608]
fps = 60


def deg_to_px(deg):
    # degrees * pixels / degree = pixels
    px_mag = (dlp_screen[0] - dlp_screen[0]/2)
    px = deg*px_mag/180

    return px


def deg_to_px_pos(deg):
    return deg_to_px(deg) + dlp_screen[0]/2


def deg_to_abs(deg):
    return deg/180


class VideoStimPlaylist(object):

    def __init__(self, *stims, random=None, paused=False, play_item=None):
        self._stims = collections.OrderedDict()
        for s in stims:
            s.show = False
            self._stims[s.identifier] = s

        self._paused = paused
        self._started_paused_and_never_played = paused

        if random is None:
            random = Randomizer(*self._stims.keys())
        self._random = random
        self._playlist_iter = self._random.iter_items()

        self._log = logging.getLogger('flyvr.video.VideoStimPlaylist')
        self._log.debug('playlist %r' % self._random)

        if play_item:
            self.play_item(play_item)
        elif not self._paused:
            self.play_item(next(self._playlist_iter))

    def initialize(self, win):
        [s.initialize(win) for s in self._stims.values()]

    def update_and_draw(self, *args, **kwargs):
        if self._paused:
            return

        for s in self._stims.values():
            s.update_and_draw(*args, **kwargs)

    def advance(self):
        if self._paused:
            return

        next_id = None
        for s in self._stims.values():
            if s.show:
                if s.is_finished:
                    try:
                        next_id = next(self._playlist_iter)
                    except StopIteration:
                        self.play_pause(pause=True)
                    finally:
                        break

        if next_id is not None:
            self.play_item(next_id)

    def describe(self):
        return [{id_: s.describe()} for id_, s in self._stims.items()]

    def update_params(self, identifier, **params):
        self._stims[identifier].update_params(**params)

    def play_item(self, identifier):
        for sid, s in self._stims.items():
            s.show = sid == identifier

        self._log.info('playing item: %s (and un-pausing)' % identifier)
        self._paused = False

    def play_pause(self, pause):
        self._paused = True if pause else False
        self._log.info('pausing' if pause else 'un-pause / playing')

        if self._started_paused_and_never_played:
            self.play_item(next(self._playlist_iter))
            self._started_paused_and_never_played = False

    def play(self, stim):
        self._stims[stim.identifier] = stim
        self.play_item(stim.identifier)


class VideoStim(object):
    NAME = 'grating'
    NUM_VIDEO_FIELDS = 7

    def __init__(self, **params):
        self._id = params.pop('identifier', uuid.uuid4().hex)
        self._duration = params.pop('duration', np.inf)
        self._show = params.pop('show', True)
        self._log = logging.getLogger('flyvr.video.%s' % self.__class__.__name__)

        self.p = Dottable(params)
        self.frame_count = 0

    @property
    def show(self):
        return self._show

    @show.setter
    def show(self, v):
        self._show = v
        self._log.debug("%s '%s'" % ('show' if v else 'hide', self._id))
        self.frame_count = 0

    @property
    def identifier(self):
        return str(self._id)[:32]

    @property
    def duration(self):
        """ return the duration of this stimulus in frames """
        return self._duration

    @property
    def is_finished(self):
        """ overridable property for stimuli to determine by other means when they are finished """
        return self.frame_count > self.duration

    def initialize(self, win):
        raise NotImplementedError

    def advance(self):
        pass

    def update_and_draw(self, *args, **kwargs):
        if self.show:
            self.update(*args, **kwargs)
            self.draw()
            self.frame_count += 1

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


# noinspection PyUnresolvedReferences
class SweepingSpotStim(VideoStim):
    NAME = 'sweeping_spot'
    NUM_VIDEO_FIELDS = 7
    # 4s OFF
    # 4s BG
    # 20s STIM
    # 4s BG
    # 4s OFF

    # RF finder/sweeping spot
    # Natural spot
    # Grating + Natural spot
    # Looming spot
    # 3D fly

    def __init__(self, radius=5, velx=1, offset=(0.2, 0),
                 init_pos=0, end_pos=1,
                 bg_color=0, fg_color=-1, off_time=4, bg_time=4, fps=60,
                 **kwargs):
        super().__init__(radius=float(radius),
                         velx=float(velx),
                         offset=[float(offset[0]), float(offset[1])],
                         init_pos=float(init_pos), end_pos=float(end_pos),
                         bg_color=float(bg_color), fg_color=float(fg_color),
                         off_time=float(off_time), bg_time=float(bg_time),
                         fps=float(fps), **kwargs)

        self.screen = None

    def initialize(self, win):
        self.screen = visual.Circle(win=win,
                                    radius=deg_to_px(self.p.radius), pos=[deg_to_px(self.p.init_pos),0],
                                    lineColor=None, fillColor=self.p.fg_color)

    @property
    def is_finished(self):
        return self.screen and (self.screen.pos[0] > deg_to_px(self.p.end_pos))

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        self.screen.pos += [deg_to_px(self.p.velx)/fps, 0]

        logger.log(self.log_name(),
                   np.array([frame_num,
                             self.p.bg_color,
                             0,
                             self.screen.pos[0], self.screen.pos[1],
                             self.screen.radius, self.screen.radius]))

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


STIMS = (NoStim, GratingStim, MovingSquareStim, LoomingStim, MayaModel, OptModel, PipStim, SweepingSpotStim)


def stimulus_factory(name, **params):
    for s in STIMS:
        if name == s.NAME:
            return s(**params)
    raise ValueError("VideoStimulus '%s' not found" % name)


class VideoServer(object):

    def __init__(self, stim=None, shared_state=None, calibration_file=None, use_lightcrafter=True):
        self._log = logging.getLogger('flyvr.video_server')

        self._initial_stim = stim
        self._save_frames_path = None

        self.stim = self.mywin = self.synchRect = self.framepacker = self.warper = None

        self.use_lightcrafter = False
        if use_lightcrafter:
            dlplc = LightCrafterTCP()
            self._log.debug("attempting to setup lightcrafter: %r" % dlplc)
            if dlplc.connect():
                # noinspection PyBroadException
                try:
                    dlplc.cmd_current_display_mode(0x02)
                    dlplc.cmd_current_video_mode(frame_rate=60, bit_depth=7, led_color=4)
                    self.use_lightcrafter = True
                except Exception:
                    self._log.error("error configuring DLP", exc_info=True)
            else:
                self._log.warning("could not configure: %r" % dlplc)

        self._log.info("%sshowing visual stimulus on lightcrafter" % ('' if self.use_lightcrafter else 'not '))

        self.samples_played = self.sync_signal = 0
        self.calibration_file = calibration_file

        # We will update variables related to audio playback in flyvr's shared state data if provided
        self.flyvr_shared_state = shared_state
        self.logger = shared_state.logger

        self._running = False
        self._q = queue.Queue()

        self.logger.create("/video/daq_synchronization_info", shape=[1024, 2], maxshape=[None, 2],
                           dtype=np.int64,
                           chunks=(1024, 2))
        for stimcls in STIMS:
            stimcls.create_log(self.logger)

    # This is how many records of calls to the callback function we store in memory.
    CALLBACK_TIMING_LOG_SIZE = 10000

    @property
    def queue(self):
        return self._q

    def _play(self, stim):
        self._log.info("playing: %r" % stim)
        if isinstance(stim, (VideoStim, VideoStimPlaylist)):
            assert self.mywin
            stim.initialize(self.mywin)
            self.stim = stim
        elif isinstance(stim, str):
            if stim in {'play', 'pause'}:
                if isinstance(self.stim, VideoStimPlaylist):
                    self.stim.play_pause(pause=stim == 'pause')
            else:
                self.stim.play_item(stim)

    def play(self, item):
        self._q.put(item)

    # noinspection PyUnusedLocal
    def quit(self, *args, **kwargs):
        self._running = False

    def run(self):
        """
        The main process function for the video server. Handles actually setting up the videodevice object\stream.
        Waits to receive objects to play on the stream, sent from other processes using a Queue or Pipe.

        :return: None
        """
        self._running = True

        self.mywin = visual.Window([608, 684],
                                   monitor='DLP',
                                   screen=1 if self.use_lightcrafter else 0,
                                   useFBO=True, color=0)
        if self.use_lightcrafter:
            self.framepacker = ProjectorFramePacker(self.mywin)
            self._log.debug('attached framepacker for lightcrafter')

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

        while self._running and self.flyvr_shared_state.is_running_well():

            try:
                msg = self._q.get_nowait()
                if isinstance(msg, (VideoStim, VideoStimPlaylist, str)):
                    self._play(msg)
                elif msg is not None:
                    self._log.error('unsupported message: %r' % msg)
            except queue.Empty:
                pass

            if self.stim is not None:
                self.stim.update_and_draw(self.mywin, self.logger, frame_num=self.samples_played)

                if self._save_frames_path:
                    self.mywin.getMovieFrame()
                    self.mywin.saveMovieFrames(
                        os.path.join(self._save_frames_path,
                                     '{}_image{:0>5d}.jpg'.format(self.stim.identifier,
                                                                  self.stim.frame_count)))

                if self.sync_signal > 60 * 10:
                    self.synchRect.fillColor = 'black'
                    self.sync_signal = 0
                elif self.sync_signal > 60 * 5:
                    self.synchRect.fillColor = 'white'

                self.synchRect.draw()
                self.mywin.flip()

                self.samples_played += 1
                self.sync_signal += 1

                self.stim.advance()

        self._log.info('exiting')


def _ipc_main(q):
    pr = PlaylistReciever()
    log = logging.getLogger('flyvr.video.ipc_main')

    log.debug('starting')

    while True:
        elem = pr.get_next_element()
        if elem:
            # noinspection PyBroadException
            try:
                if 'video' in elem:
                    defn = elem['video']
                    stim = stimulus_factory(defn['name'], **defn.get('configuration', {}))
                    q.put(stim)
                elif 'video_item' in elem:
                    q.put(elem['video_item']['identifier'])
                elif 'video_action' in elem:
                    q.put(elem['video_action'])
                else:
                    log.debug("ignoring message: %r" % elem)
            except Exception:
                log.error('could not parse playlist item', exc_info=True)

    log.debug('exiting')


def run_video_server(options):
    from flyvr.common import SharedState, Randomizer
    from flyvr.common.logger import DatasetLogServerThreaded

    setup_logging(options)

    log = logging.getLogger('flyvr.video.main')

    startup_stim = None
    playlist_stim = None
    stim_playlist = options.playlist.get('video')

    if stim_playlist:
        option_item_defn = None

        stims = []
        for item_def in stim_playlist:
            id_, defn = item_def.popitem()

            if id_ == Randomizer.IN_PLAYLIST_IDENTIFIER:
                option_item_defn = {id_: defn}
                continue

            stims.append(stimulus_factory(defn.pop('name'), identifier=id_, **defn))

        random = Randomizer.new_from_playlist_option_item(option_item_defn,
                                                          *[s.identifier for s in stims])
        playlist_stim = VideoStimPlaylist(*stims, random=random,
                                          paused=getattr(options, 'paused', False),
                                          play_item=getattr(options, 'play_item', None))

        log.info('initializing video playlist')

    elif getattr(options, 'play_stimulus'):
        startup_stim = stimulus_factory(options.play_stimulus)
        log.info('selecting single visual stimulus: %s' % options.play_stimulus)

    with DatasetLogServerThreaded() as log_server:
        logger = log_server.start_logging_server(options.record_file.replace('.h5', '.video_server.h5'))
        state = SharedState(options=options, logger=logger)

        video_server = VideoServer(stim=startup_stim,
                                   calibration_file=options.screen_calibration,
                                   shared_state=state,
                                   use_lightcrafter=not getattr(options, 'disable_projector', False))

        if playlist_stim is not None:
            video_server.play(playlist_stim)

        ipc = threading.Thread(daemon=True, name='VideoIpcThread',
                               target=_ipc_main, args=(video_server.queue,))
        ipc.start()

        video_server.run()  # blocks

        log.debug('exiting')


def main_video_server():
    from flyvr.common.build_arg_parser import build_argparser, parse_options

    parser = build_argparser()
    parser.add_argument('--disable-projector', action='store_true', help='Do not setup projector')
    parser.add_argument('--play-item', help='Play this item from the playlist',
                        metavar='IDENTIFIER')
    parser.add_argument('--play-stimulus', help='Play this stimulus only (no playlist is loaded). '
                                                'useful for testing',
                        choices=[c.NAME for c in STIMS])
    parser.add_argument('--paused', action='store_true', help='start paused')
    options = parse_options(parser.parse_args(), parser)

    run_video_server(options)
