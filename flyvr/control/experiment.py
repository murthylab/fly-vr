import re
import time
import operator
import collections

import yaml
import numpy as np

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

    def __init__(self, state_getter_callable, comparison_operator, absolute_comparison, value):
        self._c = state_getter_callable
        self._op = comparison_operator
        self._value = value
        self._abs = abs if absolute_comparison else lambda x: x

    def __repr__(self):
        return "<%s(%s %s %s)>" % (self.__class__.__name__, self._c, self._op, self._value)

    def perform(self, state):
        pass

    def calculate(self, state):
        return self._abs(self._c(state))

    def check(self, state):
        # call this directly to save a little time
        if self._op(self._abs(self._c(state)), self._value):
            self.perform(state)


class PrintEvent(_Event):

    def perform(self, state):
        print(self.calculate(state))


class Experiment(object):

    def __init__(self, events=(), timed=()):
        self._events = events
        self._timed = timed
        self._t0 = time.time()

        self._ipc = PlaylistSender()

    def start(self, uuid=None):
        self._t0 = time.time()
        self._ipc.process(command='start', value=uuid)
        return uuid

    def start_and_wait_for_all_processes(self, state):
        # todo: loop over shared mem ready vals waiting for them to be set to the uuid
        # todo: in other process (audio, daq, video) wait for ipc start command over IPC and set shmem in response
        uuid = self.start()

    @classmethod
    def from_yaml(cls, stream_like):
        dat = yaml.load(stream_like, Loader=yaml.SafeLoader)
        return cls.from_items(dat.get('state', {}), dat.get('time', {}))

    @classmethod
    def from_items(cls, state_item_defns, timed_item_defns):
        timed = []
        events = []

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

                kw = dict(state_getter_callable=state_getter,
                          comparison_operator=operator_,
                          absolute_comparison=absolute,
                          value=value)

                if type_ == 'print':
                    evt = PrintEvent(**kw)
                else:
                    evt = _Event(**kw)

                events.append(evt)

        return cls(events, timed)

    @classmethod
    def new_from_python_file(cls, path):
        _locals = {}
        with open(path) as f:
            exec(f.read(), {}, _locals)
        try:
            _experiment = _locals['experiment']
            if not isinstance(_experiment, Experiment):
                raise ValueError
            return _experiment
        except (KeyError, ValueError):
            raise RuntimeError('experiment python file must define single variable of type Experiment')

    def process_state(self, state):
        for e in self._events:
            e.check(state)

        dt = time.time() - self._t0
        for t in self._timed:
            t.check(dt)


def do_loop(exp, delay):
    from flyvr.common import SharedState

    flyvr_state = SharedState(None, None)
    data = flyvr_state._fictrac_shmem_state
    old_frame_count = data.frame_cnt

    while flyvr_state.is_running_well():
        new_frame_count = data.frame_cnt
        if old_frame_count != new_frame_count:
            exp.process_state(data)
            old_frame_count = new_frame_count
            time.sleep(delay)


def main_experiment():
    import sys
    from flyvr.common.build_arg_parser import parse_arguments

    try:
        options = parse_arguments()
    except ValueError as ex:
        sys.stderr.write("Invalid Config Error: \n" + str(ex) + "\n")
        sys.exit(-1)

    if not options.experiment:
        sys.stderr.write("No experiment specified")
        sys.exit(-1)

    do_loop(options.experiment, 1/200.)
