import re
import time
import logging
import os.path
import operator
import collections
import importlib.util

from typing import Optional

import yaml
import numpy as np

from flyvr.common import BACKEND_VIDEO as _BACKEND_VIDEO, BACKEND_DAQ as _BACKEND_DAQ,\
    BACKEND_AUDIO as _BACKEND_AUDIO, Randomizer, SharedState
from flyvr.common.ipc import PlaylistSender


class _MovingAverageStateVariable(object):

    def __init__(self, name_or_getter, num_frames_mean=25, name=''):
        if isinstance(name_or_getter, str):
            self._getter = operator.attrgetter(name)
        else:
            self._getter = name_or_getter
        self._name = name or repr(self._getter)
        self._hist = collections.deque(maxlen=num_frames_mean)

    def __repr__(self):
        return "<MovingAverageStateVariable(%s, %s)>" % (self._name, self._hist.maxlen)

    def __call__(self, state):
        self._hist.append(self._getter(state))
        return np.mean(self._hist)


class _Event(object):

    def __init__(self, state_getter_callable, comparison_operator, absolute_comparison, value, dt):
        self._c = state_getter_callable
        self._op = comparison_operator
        self._value = value
        self._abs = abs if absolute_comparison else lambda x: x
        self._dt = dt
        self._switched = False

    def __repr__(self):
        return "<%s(%s %s %s, dt=%s)>" % (self.__class__.__name__, self._c, self._op, self._value, self._dt)

    def perform(self, state, experiment):
        pass

    def calculate(self, state):
        return self._abs(self._c(state))

    def check(self, state, experiment):
        # call this directly to save a little time
        if self._op(self._abs(self._c(state)), self._value):
            self.perform(state, experiment)

    def check_dt(self, dt, state, experiment):
        if (dt > self._dt) and (not self._switched):
            self.perform(state, experiment)
            self._switched = True


class PrintEvent(_Event):

    def perform(self, state, experiment):
        print(self.calculate(state))


class PlaylistItemEvent(_Event):

    def __init__(self, *args, **kwargs):
        self._playlist_backend = kwargs.pop('backend')
        assert self._playlist_backend in (Experiment.BACKEND_VIDEO, Experiment.BACKEND_DAQ, Experiment.BACKEND_AUDIO)
        self._playlist_identifier = kwargs.pop('identifier')
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return "<%s(backend=%s, identifier=%s, dt=%s)>" % (self.__class__.__name__, self._playlist_backend, self._playlist_identifier, self._dt)

    def perform(self, state, experiment):
        experiment.play_playlist_item(self._playlist_backend, self._playlist_identifier)


class Experiment(object):

    BACKEND_VIDEO, BACKEND_AUDIO, BACKEND_DAQ = _BACKEND_VIDEO, _BACKEND_AUDIO, _BACKEND_DAQ

    def __init__(self, events=(), timed=()):
        self._events = events
        self._timed = timed
        self._t0 = time.time()

        self._playlist = {}
        self._ipc = PlaylistSender()

        self._shared_state = None  # type: Optional[SharedState]

        self.log = logging.getLogger('flyvr.experiment.%s' % self.__class__.__name__)

    def _log_describe(self):
        for evt in self._events:
            self.log.debug('state-based event: %r' % evt)
        for evt in self._timed:
            self.log.debug('time-based event: %r' % evt)

    def start(self, uuid=None):
        self._t0 = time.time()
        self._ipc.process(command='start', value=uuid)
        return uuid

    def _set_shared_state(self, shared_state: Optional[SharedState]):
        self._shared_state = shared_state

    def _set_playlist(self, playlist):
        def _get_playlist_ids(_stim_playlist):
            _ids = []

            for item_def in _stim_playlist:
                assert len(item_def) == 1
                _id = tuple(item_def.keys())[0]

                if _id == Randomizer.IN_PLAYLIST_IDENTIFIER:
                    continue

                _ids.append(_id)

            return _ids

        for k in (_BACKEND_AUDIO, _BACKEND_VIDEO, _BACKEND_DAQ):
            self._playlist[k] = _get_playlist_ids(playlist.get(k, []))

    def is_backend_ready(self, backend):
        if self._shared_state:
            return self._shared_state.is_backend_ready(backend)

    def is_started(self):
        if self._shared_state:
            return self._shared_state.is_started()

    def is_stopped(self):
        if self._shared_state:
            return self._shared_state.is_stopped()

    @property
    def configured_playlist_items(self):
        """
        returns a list of the configured playlist item identifiers for every backend. the list is in
        the same order as defined in the playlist yaml.
        """
        return dict(self._playlist)

    def play_playlist_item(self, backend, identifier):
        assert backend in (Experiment.BACKEND_VIDEO, Experiment.BACKEND_AUDIO, Experiment.BACKEND_DAQ)
        self._ipc.process(**{'%s_item' % backend: {'identifier': identifier}})

    def play_backend_item(self, backend, **conf):
        assert backend in (Experiment.BACKEND_VIDEO, Experiment.BACKEND_AUDIO, Experiment.BACKEND_DAQ)
        self._ipc.process(**{backend: conf})

    def backend_action(self, backend, action):
        assert backend in (Experiment.BACKEND_VIDEO, Experiment.BACKEND_AUDIO, Experiment.BACKEND_DAQ)
        self._ipc.process(**{'%s_action' % backend: action})

    def item_mutate(self, backend, identifier, attribute, value):
        self._ipc.process(**{'%s_mutate' % backend: (identifier, attribute, value)})

    @classmethod
    def from_yaml(cls, stream_like):
        dat = yaml.load(stream_like, Loader=yaml.SafeLoader)
        return cls.from_items(dat.get('state', {}), dat.get('time', {}))

    @classmethod
    def from_items(cls, state_item_defns, timed_item_defns):
        timed = []
        events = []

        def _evt_factory(_evt_type, _evt_conf, **_kw):
            if _evt_type == 'print':
                return PrintEvent(**_kw)
            elif _evt_type == 'playlist_item':
                _kw.update(_evt_conf)
                return PlaylistItemEvent(**_kw)
            else:
                return _Event(**_kw)

        for param, defn in state_item_defns.items():
            comparison, action_defn = defn.popitem()
            operator_ = getattr(operator, comparison)

            avg = action_defn.pop('average', 1)
            absolute = bool(action_defn.pop('absolute', False))
            value = action_defn.pop('value')
            event_definitions = action_defn.pop('do')

            full_param = param
            m = re.match(r"""([\w_]+)\[(\d)\]""", param)
            if m:
                param, idx, = m.groups()
                _getter = lambda _s, _idx=operator.itemgetter(int(idx)), _attr=operator.attrgetter(param): _idx(_attr(_s))
            else:
                _getter = operator.attrgetter(param)

            if avg == 1:
                state_getter = _getter
            else:
                state_getter = _MovingAverageStateVariable(_getter, int(avg), name=full_param)

            for evt in event_definitions:
                type_, evt_conf = evt.popitem()

                evt = _evt_factory(type_, evt_conf,
                                   state_getter_callable=state_getter,
                                   comparison_operator=operator_,
                                   absolute_comparison=absolute,
                                   value=value,
                                   dt=None)
                events.append(evt)

        for _t, defn in timed_item_defns.items():
            t = float(_t) / 1000.
            event_definitions = defn.pop('do')

            for evt in event_definitions:
                type_, evt_conf = evt.popitem()

                evt = _evt_factory(type_, evt_conf,
                                   state_getter_callable=None,
                                   comparison_operator=None,
                                   absolute_comparison=None,
                                   value=None,
                                   dt=t)
                timed.append(evt)

        return cls(events, timed)

    @classmethod
    def new_from_python_file(cls, path):
        def _module_from_file():
            module = None
            try:
                module_dir, module_file = os.path.split(path)
                module_name, module_ext = os.path.splitext(module_file)
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = spec.loader.load_module()
            except Exception as exc:
                raise RuntimeError('could not import experiment: %s' % exc)
            finally:
                return module

        mod = _module_from_file()
        try:
            exp = getattr(mod, 'experiment')
            if not isinstance(exp, Experiment):
                raise ValueError('experiment python file must define single variable of type Experiment')
            return exp
        except AttributeError:
            raise RuntimeError('experiment python file must define single variable of type Experiment')

    def process_state(self, state):
        for e in self._events:
            e.check(state, self)

        dt = time.time() - self._t0
        for t in self._timed:
            t.check_dt(dt, state, self)


def do_loop(exp, delay, force=False):
    from flyvr.common import SharedState

    flyvr_state = SharedState(None, None)
    data = flyvr_state._fictrac_shmem_state
    old_frame_count = data.frame_cnt

    while flyvr_state.is_running_well():
        new_frame_count = data.frame_cnt
        if (old_frame_count != new_frame_count) or force:
            exp.process_state(data)
            old_frame_count = new_frame_count
            time.sleep(delay)


def main_experiment():
    from flyvr.common.build_arg_parser import build_argparser, parse_options, setup_experiment, setup_logging

    parser = build_argparser()
    parser.add_argument('--force', action='store_true', help='force/fake iterate at 200fps even if no tracking data '
                        'is present (for testing)')

    options = parse_options(parser.parse_args(), parser)
    setup_logging(options)

    setup_experiment(options)
    if not options.experiment:
        parser.error("No experiment specified")

    # noinspection PyProtectedMember
    options.experiment._set_shared_state(SharedState(options=options, logger=None))

    # noinspection PyProtectedMember
    options.experiment._log_describe()
    do_loop(options.experiment, 1/200., options.force)
