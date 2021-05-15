import uuid
import time
import queue
import os.path
import logging
import threading
import collections
import pkg_resources

import h5py
import numpy as np

from flyvr.common import Randomizer, BACKEND_VIDEO
from flyvr.common.dottable import Dottable
from flyvr.common.build_arg_parser import setup_logging
from flyvr.projector.dlplc_tcp import LightCrafterTCP
from flyvr.common.ipc import PlaylistReciever

from PIL import Image
from psychopy import visual, core, event
from psychopy.visual.windowwarp import Warper
from psychopy.visual.windowframepack import ProjectorFramePacker


SYNCHRONIZATION_INFO_FIELDS = ('fictrac_frame_num',
                               'daq_output_num_samples_written',
                               'daq_input_num_samples_read',
                               'sound_output_num_samples_written',
                               'video_output_num_frames',
                               'time_ns',
                               'producer_instance_n', 'producer_playlist_n')
SYNCHRONIZATION_INFO_NUM_FIELDS = len(SYNCHRONIZATION_INFO_FIELDS)


dlp_screen = [684, 608]


def package_data_filename(filename_relative_to_datadir):
    return pkg_resources.resource_filename('flyvr', os.path.join('data', filename_relative_to_datadir))


def deg_to_px(deg):
    # degrees * pixels / degree = pixels
    px_mag = (dlp_screen[0] - dlp_screen[0]/2)
    px = deg*px_mag/180

    return px


def deg_to_px_pos(deg):
    return deg_to_px(deg) + dlp_screen[0]/2


def deg_to_abs(deg):
    return deg/180


class _NoVideoStim(object):
    producer_playlist_n = -2
    producer_instance_n = -2


class VideoStimPlaylist(object):

    def __init__(self, *stims, random=None, paused=False, play_item=None):
        self._log = logging.getLogger('flyvr.video.VideoStimPlaylist')

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

        self._log.info('playlist paused: %s order: %r' % (paused, self._random))

        self._flyvr_shared_state = None
        self._child_playlist_n = 0

        if play_item:
            self.play_item(play_item)
        elif not self._paused:
            self.play_item(next(self._playlist_iter))

    def __getitem__(self, item):
        return self._stims[item]

    def initialize(self, win, fps, flyvr_shared_state):
        self._flyvr_shared_state = flyvr_shared_state
        [s.initialize(win, fps, flyvr_shared_state) for s in self._stims.values()]

    def update_and_draw(self, *args, **kwargs):
        if self._paused:
            return

        active_stim = None
        for s in self._stims.values():
            active_stim = active_stim or s.update_and_draw(*args, **kwargs)

        return active_stim

    def advance(self):
        if self._paused:
            return True

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

        return True

    def describe(self):
        return [{id_: s.describe()} for id_, s in self._stims.items()]

    def update_params(self, identifier, **params):
        self._stims[identifier].update_params(**params)

    def play_item(self, identifier):
        producer_instance_n = None

        for sid, s in self._stims.items():
            if sid == identifier:
                s.show = True
                s.producer_playlist_n = self._child_playlist_n
                producer_instance_n = s.producer_instance_n
            else:
                s.show = False
                s.producer_playlist_n = -1

        if producer_instance_n is not None:
            # we found the item
            self._log.info('playing item: %s (and un-pausing)' % identifier)
            self._paused = False

            if self._flyvr_shared_state is not None:
                self._flyvr_shared_state.signal_new_playlist_item(identifier, BACKEND_VIDEO,
                                                                  producer_instance_n=producer_instance_n,
                                                                  producer_playlist_n=self._child_playlist_n,
                                                                  # and a time for replay experiments
                                                                  time_ns=time.time_ns())

            self._child_playlist_n += 1

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

    NAME = None

    H5_FIELDS = ()

    instances_created = 0

    def __init__(self, **params):
        self._id = params.pop('identifier', uuid.uuid4().hex)

        self._duration_frames = params.pop('duration_frames', np.inf)
        self._duration_seconds = params.pop('duration_seconds', None)

        self._show = params.pop('show', True)
        self._log = logging.getLogger('flyvr.video.%s' % self.__class__.__name__)

        self._fps = None

        self._h5_log_name = "/video/stimulus/{}".format(self.NAME)

        self.p = Dottable(params)
        self.frame_count = 0

        self.producer_playlist_n = -1
        self.producer_instance_n = VideoStim.instances_created
        VideoStim.instances_created += 1

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
        return self._duration_frames

    @property
    def elapsed_time(self):
        """ returns """
        return self.frame_count / self._fps

    @property
    def is_finished(self):
        """ overridable property for stimuli to determine by other means when they are finished """
        return self.frame_count > self.duration

    def initialize(self, win, fps, flyvr_shared_state):
        self._fps = fps
        if np.isinf(self._duration_frames) and (self._duration_seconds is not None):
            self._duration_frames = int(fps * self._duration_seconds)
            self._log.debug('set duration for %d frames @ %f fps' % (self._duration_frames, fps))

    def advance(self):
        """ can return False when there is no further item to advance to. in the single stimulus case
        this indicates the stimulus is finished """
        return not self.is_finished

    def update_and_draw(self, *args, **kwargs):
        if self.show:
            self.update(*args, **kwargs)
            self.draw()
            self.frame_count += 1
            return self

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
    def create_h5_log(cls, logger):
        if cls.H5_FIELDS and (cls.H5_FIELDS[0] == 'video_output_num_frames'):
            pass
        else:
            raise Exception('VideoStim defines no fields or log or field_0 is not video_output_num_frames')

        log_name = "/video/stimulus/{}".format(cls.NAME)

        n = len(cls.H5_FIELDS)
        logger.create(log_name,
                      shape=[2048, n],
                      maxshape=[None, n], dtype=np.float64,
                      chunks=(2048, n))

        for cn, cname in enumerate(cls.H5_FIELDS):
            logger.log(log_name, str(cname), attribute_name='column_%d' % cn)

    def h5_log(self, logger, frame_num, *fields):
        row = [frame_num]
        row.extend(fields)

        if len(row) != len(self.H5_FIELDS):
            raise Exception('incorrect row %r for defined fields: %r' % (row, self.H5_FIELDS))

        logger.log(self._h5_log_name, np.array(row, dtype=np.float64))


class NoStim(VideoStim):
    NAME = 'none'

    H5_FIELDS = ('video_output_num_frames', )

    def update(self, win, logger, frame_num):
        self.h5_log(logger, frame_num)

    def draw(self):
        pass


class GratingStim(VideoStim):
    NAME = 'grating'

    NUM_VIDEO_FIELDS = 7
    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'sf',
                 'stim_size',
                 'stim_color',
                 'phase')

    def __init__(self, sf=50, stim_size=5, stim_color=-1, bg_color=0.5, **kwargs):
        super().__init__(sf=int(sf),
                         stim_size=int(stim_size),
                         stim_color=int(stim_color),
                         bg_color=float(bg_color), **kwargs)
        self.screen = None

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self.screen = visual.GratingStim(win=win, size=self.p.stim_size,
                                         pos=[0, 0], sf=self.p.sf,
                                         color=self.p.stim_color, phase=0)

    def update(self, win, logger, frame_num):
        self.screen.setPhase(0.05, '+')
        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            1,
                            self.p.sf,
                            self.p.stim_size,
                            self.p.stim_color,
                            self.screen.phase[0])

    def draw(self):
        self.screen.draw()


class SweepingSpotStim(VideoStim):
    NAME = 'sweeping_spot'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'radius',
                 '?radius')

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

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self.screen = visual.Circle(win=win,
                                    radius=deg_to_px(self.p.radius), pos=[deg_to_px(self.p.init_pos), 0],
                                    lineColor=None, fillColor=self.p.fg_color)

    @property
    def is_finished(self):
        return self.screen and (self.screen.pos[0] > deg_to_px(self.p.end_pos))

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        self.screen.pos += [deg_to_px(self.p.velx)/self._fps, 0]

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            0,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.radius, self.screen.radius)

    def draw(self):
        self.screen.draw()


class AdamStim(VideoStim):
    NAME = 'adamstim'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'size_x',
                 'size_y')

    def __init__(self, filename='pipStim.mat', offset=(0, 0), bg_color=0, fg_color=-1, **kwargs):
        super().__init__(offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)

        with h5py.File(package_data_filename(filename), 'r') as f:
            self._tdis = f['tDis'][:, 0]
            self._tang = f['tAng'][:, 0]

        self.screen = None

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self.screen = visual.Circle(win=win,
                                    radius=0, pos=self.p.offset,
                                    lineColor=None, fillColor=self.p.fg_color)

    def update(self, win, logger, frame_num):
        # noinspection DuplicatedCode
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        self.screen.pos = self._tang[round(frame_num)] / 180 + xoffset, yoffset
        self.screen.radius = 1 / self._tdis[round(frame_num)]

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            0,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.size[0], self.screen.size[1])

    def draw(self):
        self.screen.draw()


class AdamStimGrating(VideoStim):
    NAME = 'adamstimgrating'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'size_x',
                 'size_y')

    def __init__(self, filename='pipStim.mat', offset=(0, 0), bg_color=0, fg_color=-1, **kwargs):
        super().__init__(offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)

        with h5py.File(package_data_filename(filename), 'r') as f:
            self._tdis = f['tDis'][:, 0]
            self._tang = f['tAng'][:, 0]

        self.screen = self.screen2 = None

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self.screen = visual.Circle(win=win,
                                    radius=0, pos=self.p.offset,
                                    lineColor=None, fillColor=self.p.fg_color)
        self.screen2 = visual.GratingStim(win=win,
                                          pos=[0, 0], sf=50, size=10,
                                          phase=0)

    def update(self, win, logger, frame_num):
        # noinspection DuplicatedCode
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        self.screen.pos = self._tang[round(frame_num)] / 180 + xoffset, yoffset
        self.screen.radius = 1 / self._tdis[round(frame_num)]

        self.screen2.phase += 0.01

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            0,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.size[0], self.screen.size[1])

    def draw(self):
        self.screen2.draw()
        self.screen.draw()


class GenericStaticFixationStim(VideoStim):

    NAME = 'generic_fixation'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 'obj1_w',
                 'obj1_h',
                 'obj1_x',
                 'obj1_y',
                 'obj1_fg_color',
                 'obj1_r',
                 'obj1_visible',
                 'obj2_w',
                 'obj2_h',
                 'obj2_x',
                 'obj2_y',
                 'obj2_fg_color',
                 'obj2_r',
                 'obj2_visible')

    def __init__(self,
                 obj1_w=0.25, obj1_h=0.25, obj1_x=-0.2, obj1_y=0.5, obj1_fg_color=1, obj1_r=0, obj1_visible=1,
                 obj2_w=0.05, obj2_h=0.85, obj2_x=+0.2, obj2_y=0.5, obj2_fg_color=0.5, obj2_r=0, obj2_visible=1,
                 bg_color=-1, **kwargs):
        super().__init__(obj1_w=float(obj1_w), obj1_h=float(obj1_h), obj1_x=float(obj1_x), obj1_y=float(obj1_y),
                         obj1_fg_color=float(obj1_fg_color), obj1_r=float(obj1_r),
                         obj1_visible=1 if obj1_visible else 0,
                         obj2_w=float(obj2_w), obj2_h=float(obj2_h), obj2_x=float(obj2_x), obj2_y=float(obj2_y),
                         obj2_fg_color=float(obj2_fg_color), obj2_r=float(obj2_r),
                         obj2_visible=1 if obj2_visible else 0,
                         bg_color=float(bg_color), **kwargs)
        self.obj1 = None
        self._obj1_is_circle = obj1_r > 0
        self.obj2 = None
        self._obj2_is_circle = obj2_r > 0

    # noinspection DuplicatedCode
    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        if self._obj1_is_circle:
            self.obj1 = visual.Circle(win=win,
                                      radius=self.p.obj1_r,
                                      pos=(self.p.obj1_x, self.p.obj1_y),
                                      lineColor=None, fillColor=self.p.obj1_fg_color)
        else:
            self.obj1 = visual.Rect(win=win,
                                    size=(self.p.obj1_w, self.p.obj1_h),
                                    pos=(self.p.obj1_x, self.p.obj1_y),
                                    lineColor=None, fillColor=self.p.obj1_fg_color)
        if self._obj2_is_circle:
            self.obj2 = visual.Circle(win=win,
                                      radius=self.p.obj2_r,
                                      pos=(self.p.obj2_x, self.p.obj2_y),
                                      lineColor=None, fillColor=self.p.obj2_fg_color)
        else:
            self.obj2 = visual.Rect(win=win,
                                    size=(self.p.obj2_w, self.p.obj2_h),
                                    pos=(self.p.obj2_x, self.p.obj2_y),
                                    lineColor=None, fillColor=self.p.obj2_fg_color)

    def update(self, win, logger, frame_num):
        self.obj1.pos = self.p.obj1_x, self.p.obj1_y
        self.obj2.pos = self.p.obj2_x, self.p.obj2_y
        if self._obj1_is_circle:
            self.obj1.radius = self.p.obj1_r
        else:
            self.obj1.size = self.p.obj1_w, self.p.obj1_h
        if self._obj2_is_circle:
            self.obj2.radius = self.p.obj2_r
        else:
            self.obj2.size = self.p.obj2_w, self.p.obj2_h

        # collect same named fields from state in the order they were defined in H5_FIELDS
        self.h5_log(logger, frame_num, *(self.p[field] for field in self.H5_FIELDS[1:]))

    def draw(self):
        if self.p.obj1_visible:
            self.obj1.draw()
        if self.p.obj2_visible:
            self.obj2.draw()


class MovingSquareStim(VideoStim):
    NAME = 'moving_square'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'size_x',
                 'size_y')

    def __init__(self, size=(0.25, 0.25), speed=(0.01, 0), offset=(0.2, -0.5),
                 bg_color=-1, fg_color=1, **kwargs):
        super().__init__(size=[float(size[0]), float(size[1])],
                         speed=[float(speed[0]), float(speed[1])],
                         offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)
        self.screen = None

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
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

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            0,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.size[0], self.screen.size[1])

    def draw(self):
        self.screen.draw()


class PipStim(VideoStim):
    NAME = 'pipstim'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'size_x',
                 'size_y')

    def __init__(self, filename='pipStim.mat', offset=(0.2, -0.5), bg_color=-1, fg_color=1, **kwargs):
        super().__init__(offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)

        with h5py.File(package_data_filename(filename), 'r') as f:
            self._tdis = f['tDis'][:, 0]
            self._tang = f['tAng'][:, 0]

        self.screen = None

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self.screen = visual.Rect(win=win,
                                  size=(0.25, 0.25), pos=self.p.offset,
                                  lineColor=None, fillColor=self.p.fg_color)

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        self.screen.pos = self._tang[round(frame_num)] / 180 + xoffset, yoffset
        self.screen.size = 1 / self._tdis[round(frame_num)], 1 / self._tdis[round(frame_num)]

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            0,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.size[0], self.screen.size[1])

    def draw(self):
        self.screen.draw()


class LoomingStim(VideoStim):

    NAME = 'looming'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'size_x',
                 'size_y')

    def __init__(self, size_min=0.05, size_max=0.8, speed=0.01, offset=(0.2, -0.5),
                 bg_color=-1, fg_color=1, **kwargs):
        super().__init__(size_min=float(size_min), size_max=float(size_max), speed=float(speed),
                         offset=[float(offset[0]), float(offset[1])],
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)
        self.screen = None

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self.screen = visual.Rect(win=win,
                                  size=self.p.size_min, pos=self.p.offset,
                                  lineColor=None, fillColor=self.p.fg_color)

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color

        self.screen.size += self.p.speed
        if self.screen.size[0] > self.p.size_max:
            self.screen.size = (self.p.size_min, self.p.size_min)

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            0,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.size[0], self.screen.size[1])

    def draw(self):
        self.screen.draw()


class LoomingStimCircle(VideoStim):

    NAME = 'loomingcircle'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'radius',
                 '?radius')

    def __init__(self, size_min=0.05, size_max=0.8, rv=1, offset=(0.2, -0.5),
                 bg_color=-1, fg_color=1, **kwargs):
        super().__init__(size_min=float(size_min), size_max=float(size_max),
                         offset=[float(offset[0]), float(offset[1])],
                         rv=float(rv),
                         bg_color=float(bg_color), fg_color=float(fg_color), **kwargs)

        # adam defined this per default in terms of seconds which means it crashes if a defult is not
        # supplied. So check this post constuction so we can make a warning
        if np.isinf(self._duration_frames) and (self._duration_seconds is None):
            self._log.warning('this stimulus requires a duration - setting default to 3s')
            self._duration_seconds = 3

        self.screen = None

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self.screen = visual.Circle(win=win,
                                    radius=self.p.size_min, pos=self.p.offset,
                                    lineColor=None, fillColor=self.p.fg_color)

    def update(self, win, logger, frame_num):
        win.color = self.p.bg_color
        time_countdown = self._duration_seconds - self.elapsed_time

        self.screen.radius = deg_to_px(self.p.size_max/(np.pi/2) * np.arctan(self.p.rv / time_countdown))

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            0,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.radius, self.screen.radius)

    def draw(self):
        self.screen.draw()


class MayaModel(VideoStim):

    NAME = 'maya_model'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'size_x',
                 'size_y')

    def __init__(self, bg_color=(178 / 256) * 2 - 1, frame_start=10000, offset=(0.2, -0.5), **kwargs):
        super().__init__(bg_color=float(bg_color),
                         offset=[float(offset[0]), float(offset[1])], **kwargs)

        self._imgs = self.screen = None
        self._image_names = [package_data_filename('mayamodel/femalefly360deg/fly' + str(img_num) + '.png')
                             for img_num in range(-179, 181)]

        angles = np.load(package_data_filename('mayamodel/angles_fly19.npy'))
        top_y = np.load(package_data_filename('mayamodel/tops_fly19.npy'))
        bottom_y = np.load(package_data_filename('mayamodel/bottoms_fly19.npy'))
        left_x = np.load(package_data_filename('mayamodel/lefts_fly19.npy'))
        right_x = np.load(package_data_filename('mayamodel/rights_fly19.npy'))

        self._angles = angles[frame_start:]
        self._img_pos = [(left_x[frame_start:] + right_x[frame_start:]) / 2,
                         (top_y[frame_start:] + bottom_y[frame_start:]) / 2]
        self._img_size = [right_x[frame_start:] - left_x[frame_start:],
                          top_y[frame_start:] - bottom_y[frame_start:]]

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self._imgs = [visual.ImageStim(win=win, image=Image.open(i).convert('L')) for i in self._image_names]
        self.screen = self._imgs[0]

    def update(self, win, logger, frame_num):
        # noinspection DuplicatedCode
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        # right now moving at 30 Hz but projecting at 60 Hz
        self.screen = self._imgs[self._angles[round(frame_num / 2)]]
        self.screen.pos = [self._img_pos[0][round(frame_num / 2)] + xoffset,
                           self._img_pos[1][round(frame_num / 2)] + yoffset]
        self.screen.size = [self._img_size[0][round(frame_num / 2)],
                            self._img_size[1][round(frame_num / 2)]]

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            2,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.size[0], self.screen.size[1])

    def draw(self):
        self.screen.draw()


class OptModel(VideoStim):

    NAME = 'opt_model'

    H5_FIELDS = ('video_output_num_frames',
                 'bg_color',
                 '?',
                 'pos_x',
                 'pos_y',
                 'size_x',
                 'size_y')

    def __init__(self, bg_color=(178 / 256) * 2 - 1, offset=(0.2, -0.5), **kwargs):
        super().__init__(bg_color=float(bg_color),
                         offset=[float(offset[0]), float(offset[1])], **kwargs)

        self._imgs = self.screen = None

        self._image_names = [package_data_filename('mayamodel/femalefly360deg/fly' + str(i) + '.png')
                             for i in range(-179, 181)]

        angles_v = np.load(package_data_filename('mayamodel/forwardvelocity/angles_optstim.npy'))

        ty_v = np.load(package_data_filename('mayamodel/forwardvelocity/tops_optstim.npy'))
        by_v = np.load(package_data_filename('mayamodel/forwardvelocity/bottoms_optstim.npy'))
        lx_v = np.load(package_data_filename('mayamodel/forwardvelocity/lefts_optstim.npy'))
        rx_v = np.load(package_data_filename('mayamodel/forwardvelocity/rights_optstim.npy'))

        angles_p = np.load(package_data_filename('mayamodel/pulse/angles_optstim.npy'))

        ty_p = np.load(package_data_filename('mayamodel/pulse/tops_optstim.npy'))
        by_p = np.load(package_data_filename('mayamodel/pulse/bottoms_optstim.npy'))
        lx_p = np.load(package_data_filename('mayamodel/pulse/lefts_optstim.npy'))
        rx_p = np.load(package_data_filename('mayamodel/pulse/rights_optstim.npy'))

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

    def initialize(self, win, fps, flyvr_shared_state):
        super().initialize(win, fps, flyvr_shared_state)
        self._imgs = [visual.ImageStim(win=win, image=Image.open(i).convert('L')) for i in self._image_names]
        self.screen = self._imgs[0]

    def update(self, win, logger, frame_num):
        # noinspection DuplicatedCode
        win.color = self.p.bg_color

        xoffset, yoffset = self.p.offset

        # right now moving at 30 Hz but projecting at 60 Hz
        self.screen = self._imgs[self._angles[round(frame_num / 2)]]
        self.screen.pos = [self._img_pos[0][round(frame_num / 2)] + xoffset,
                           self._img_pos[1][round(frame_num / 2)] + yoffset]
        self.screen.size = [self._img_size[0][round(frame_num / 2)],
                            self._img_size[1][round(frame_num / 2)]]

        self.h5_log(logger, frame_num,
                            self.p.bg_color,
                            2,
                            self.screen.pos[0], self.screen.pos[1],
                            self.screen.size[0], self.screen.size[1])

    def draw(self):
        self.screen.draw()


STIMS = (NoStim, GratingStim, MovingSquareStim, LoomingStim, MayaModel, OptModel, PipStim, SweepingSpotStim,
         AdamStim, AdamStimGrating, LoomingStimCircle, GenericStaticFixationStim)


def stimulus_factory(name, **params):
    for s in STIMS:
        if name == s.NAME:
            return s(**params)
    raise ValueError("VideoStimulus '%s' not found" % name)


class VideoServer(object):

    def __init__(self, shared_state=None, calibration_file=None, use_lightcrafter=True):
        self._log = logging.getLogger('flyvr.video_server')

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

        self.logger.create("/video/synchronization_info",
                           shape=[1024, SYNCHRONIZATION_INFO_NUM_FIELDS],
                           maxshape=[None, SYNCHRONIZATION_INFO_NUM_FIELDS],
                           dtype=np.int64,
                           chunks=(1024, SYNCHRONIZATION_INFO_NUM_FIELDS))
        for cn, cname in enumerate(SYNCHRONIZATION_INFO_FIELDS):
            self.logger.log("/video/synchronization_info",
                            str(cname),
                            attribute_name='column_%d' % cn)

        for stimcls in STIMS:
            stimcls.create_h5_log(self.logger)

        self.mywin = visual.Window([608, 684],
                                   monitor='DLP',
                                   screen=1 if self.use_lightcrafter else 0,
                                   useFBO=True, color=0)
        self._fps = self.mywin.getActualFrameRate()
        if self._fps is None:
            raise ValueError('could not determine monitor FPS')

        self.flyvr_shared_state.logger.log("/video/synchronization_info",
                                           float(self._fps),
                                           attribute_name='sample_rate')
        self.flyvr_shared_state.logger.log("/video/synchronization_info",
                                           1,
                                           attribute_name='sample_buffer_size')

    # This is how many records of calls to the callback function we store in memory.
    CALLBACK_TIMING_LOG_SIZE = 10000

    @property
    def queue(self):
        return self._q

    def _play(self, stim_or_cmd):
        if isinstance(stim_or_cmd, (VideoStim, VideoStimPlaylist)):
            self._log.info("playing: %r" % (stim_or_cmd,))
            assert self.mywin
            stim_or_cmd.initialize(self.mywin, self._fps, self.flyvr_shared_state)
            self.stim = stim_or_cmd
        elif isinstance(stim_or_cmd, str):
            self._log.info("playing item/action: %r" % (stim_or_cmd,))
            if stim_or_cmd in {'play', 'pause'}:
                if isinstance(self.stim, VideoStimPlaylist):
                    self.stim.play_pause(pause=stim_or_cmd == 'pause')
            else:
                self.stim.play_item(stim_or_cmd)
        elif isinstance(stim_or_cmd, tuple):
            _id, _attr, _value = stim_or_cmd
            if isinstance(self.stim, VideoStimPlaylist):
                _stim = self.stim[_id]
                setattr(_stim.p, _attr, _value)
            else:
                raise NotImplementedError

    # noinspection PyUnusedLocal
    def quit(self, *args, **kwargs):
        self._running = False

    def run(self):
        """
        The main process function for the video server. Handles actually setting up the videodevice object / stream.
        Waits to receive objects to play on the stream, sent from other processes using a Queue or Pipe.

        :return: None
        """
        self._running = True

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
                                 warpfile=warpfile,
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

        _ = self.flyvr_shared_state.signal_ready(BACKEND_VIDEO)

        if not self.flyvr_shared_state.wait_for_start():
            self._log.info('did not receive start signal')
            self._running = False

        while self._running:

            try:
                msg = self._q.get_nowait()
                if isinstance(msg, (VideoStim, VideoStimPlaylist, str, tuple)):
                    self._play(msg)
                elif msg is not None:
                    self._log.error('unsupported message: %r' % (msg,))
            except queue.Empty:
                pass

            if self.stim is not None:
                active_stim = self.stim.update_and_draw(self.mywin, self.logger, frame_num=self.samples_played) \
                              or _NoVideoStim

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

                self.flyvr_shared_state.VIDEO_OUTPUT_NUM_FRAMES = self.samples_played
                self.logger.log("/video/synchronization_info",
                                np.array([self.flyvr_shared_state.FICTRAC_FRAME_NUM,
                                          self.flyvr_shared_state.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN,
                                          self.flyvr_shared_state.DAQ_INPUT_NUM_SAMPLES_READ,
                                          self.flyvr_shared_state.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN,
                                          self.flyvr_shared_state.VIDEO_OUTPUT_NUM_FRAMES,
                                          self.flyvr_shared_state.TIME_NS,
                                          active_stim.producer_instance_n,
                                          active_stim.producer_playlist_n], dtype=np.int64))

                if not self.stim.advance():
                    self.stim.show = False

            if self.flyvr_shared_state.is_stopped():
                self._running = False

        self._log.info('stopped')


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
                elif 'video_mutate' in elem:
                    q.put(elem['video_mutate'])
                else:
                    log.debug("ignoring message: %r" % elem)
            except Exception:
                log.error('could not parse playlist item', exc_info=True)

    # noinspection PyUnreachableCode
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
        option_item_defn = {}

        stims = []
        for item_def in stim_playlist:
            id_, defn = item_def.popitem()

            if id_ == Randomizer.IN_PLAYLIST_IDENTIFIER:
                option_item_defn = {id_: defn}
                continue

            stims.append(stimulus_factory(defn.pop('name'), identifier=id_, **defn))

        random = Randomizer.new_from_playlist_option_item(option_item_defn,
                                                          *[s.identifier for s in stims])
        paused = option_item_defn.pop('paused', None)

        playlist_stim = VideoStimPlaylist(*stims, random=random,
                                          paused=paused if paused is not None else getattr(options, 'paused', False),
                                          play_item=getattr(options, 'play_item', None))
        log.info('initialized video playlist: %r' % playlist_stim)

    elif getattr(options, 'play_stimulus', None):
        startup_stim = stimulus_factory(options.play_stimulus)
        log.info('selecting single visual stimulus: %s' % options.play_stimulus)

    with DatasetLogServerThreaded() as log_server:
        logger = log_server.start_logging_server(options.record_file.replace('.h5', '.video_server.h5'))
        state = SharedState(options=options, logger=logger, where=BACKEND_VIDEO)

        video_server = VideoServer(calibration_file=options.screen_calibration,
                                   shared_state=state,
                                   use_lightcrafter=not getattr(options, 'projector_disable', False))

        if playlist_stim is not None:
            video_server.queue.put(playlist_stim)
        elif startup_stim is not None:
            video_server.queue.put(startup_stim)

        ipc = threading.Thread(daemon=True, name='VideoIpcThread',
                               target=_ipc_main, args=(video_server.queue,))
        ipc.start()

        try:
            video_server.run()  # blocks
        except KeyboardInterrupt:
            video_server.quit()

    log.info('finished')


def main_video_server():
    from flyvr.common.build_arg_parser import build_argparser, parse_options

    parser = build_argparser()
    parser.add_argument('--play-item', help='Play this item from the playlist',
                        metavar='IDENTIFIER')
    parser.add_argument('--play-stimulus', help='Play this stimulus only (no playlist is loaded). '
                                                'useful for testing',
                        choices=[c.NAME for c in STIMS])
    parser.add_argument('--paused', action='store_true', help='start paused')
    options = parse_options(parser.parse_args(), parser)

    run_video_server(options)
