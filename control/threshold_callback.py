from audio.stimuli import SinStim
from control.callback import FlyVRCallback
from audio.sound_server import SoundServer, SoundStreamProxy
from collections import deque

class ThresholdCallback(FlyVRCallback):
    """
    This class implements control logic for triggering an audio stimulus when tracking velocity reaches a certain
    threshold.
    """

    def __init__(self, shared_state, speed_threshold=0.05, num_frames_mean=10):

        # Call the base class constructor
        super(ThresholdCallback, self).__init__(shared_state=shared_state)

        self.speed_threshold = speed_threshold
        self.num_frames_mean = num_frames_mean

    def setup_callback(self):

        # Setup the audio server for playback of sound
        self.sound_server = SoundServer(flyvr_shared_state=self.state)
        self.sound_client = self.sound_server.start_stream(frames_per_buffer=128, suggested_output_latency=0.002)

        self.stim = SinStim(frequency=200, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)

        # Our buffer of past speeds
        self.speed_history = deque(maxlen=self.num_frames_mean)

        self.is_signal_on = False


    def process_callback(self, track_state):

        # Add the speed to our history
        self.speed_history.append(track_state.speed)

        # Get the running average speed
        avg_speed = sum(self.speed_history)/len(self.speed_history)

        if avg_speed > self.speed_threshold and not self.is_signal_on:
            self.sound_client.play(self.stim)
            self.is_signal_on = True

        if avg_speed < self.speed_threshold and self.is_signal_on:
            self.sound_client.play(None)
            self.is_signal_on = False

    def shutdown_callback(self):

        # Shutdown the sound server
        self.sound_client.close()
