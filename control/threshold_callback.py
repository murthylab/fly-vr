from audio.stimuli import SinStim
from control.callback import FlyVRCallback
from audio.sound_server import SoundServer, SoundStreamProxy

class ThresholdCallback(FlyVRCallback):
    """
    This class implements control logic for triggering an audio stimulus when tracking velocity reaches a certain
    threshold.
    """

    def __init__(self, shared_state):

        # Call the base class constructor
        super(ThresholdCallback, self).__init__(shared_state=shared_state)

    def setup_callback(self):

        # Setup the audio server for playback of sound
        self.sound_server = SoundServer(flyvr_shared_state=self.state)
        self.sound_client = self.sound_server.start_stream(frames_per_buffer=128, suggested_output_latency=0.002)

        stim1 = SinStim(frequency=200, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)
        stim2 = None
        self.stims = [stim1, None]
        self.stim_idx = 0
        self.last_switch = 0
        self.SWITCH_INTERVAL = 100

    def process_callback(self, track_state):

        if track_state.frame_cnt >= self.last_switch + self.SWITCH_INTERVAL:
            self.last_switch = self.last_switch + self.SWITCH_INTERVAL
            self.sound_client.play(self.stims[self.stim_idx])
            self.stim_idx = (self.stim_idx + 1) % 2

    def shutdown_callback(self):

        # Shutdown the sound server
        self.sound_client.close()
