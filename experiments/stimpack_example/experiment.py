import time
import random
import logging

from flyvr.control.experiment import Experiment

from stimpack.visual_stim.stim_server import launch_stim_server
from stimpack.visual_stim.screen import Screen

from time import sleep

class _StimpackExample(Experiment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._log = logging.getLogger('experiments.stimpack_example.experiment')

        self._t = time.time()
        self._first = True

        # Initialize your display canvas with the default a default screen server
        self.screen = Screen(fullscreen=False, vsync=True)

        # Launch the stim server
        self.manager = launch_stim_server(self.screen)
        sleep(2)

        # Set the background color of the screen
        self.manager.set_idle_background(0.5)

        self.visual_stims = [
            dict(name='MovingSpot', radius=2.5, sphere_radius=1, color=[1, 0, 0, 1], theta=0, phi=21.5, hold=True),
            dict(name="Checkerboard")
        ]

    @property
    def is_started_and_ready_audio_daq(self):
        return self.is_started() and \
            self.is_backend_ready(Experiment.BACKEND_AUDIO) and \
            self.is_backend_ready(Experiment.BACKEND_DAQ)

    def process_state(self, state):
        dt = time.time() - self._t
        if dt > 7 and self.is_started_and_ready_audio_daq:
            astim = random.choice(('silence', 'sin800hz'))

            if astim == 'sin800hz':
                vis_stim = 0
            else:
                vis_stim = 1

            self.manager.load_stim(**self.visual_stims[vis_stim])

            # Start the stimulus
            print(f'Starting visual stim: {self.visual_stims[vis_stim]["name"]}')
            # self.manager.stop_stim(print_profile=False)
            self.manager.start_stim()

            self.play_playlist_item(Experiment.BACKEND_AUDIO, astim)
            self._t = time.time()


experiment = _StimpackExample()