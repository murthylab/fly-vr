from audio.signal_producer import ConstantSignal
from audio.stimuli import SinStim, SquareWaveStim
from control.callback import FlyVRCallback
from audio.sound_server import SoundServer, SoundStreamProxy
from collections import deque

from video.video_server import VideoServer, VideoStreamProxy

class ThresholdCallback(FlyVRCallback):
    """
    This class implements control logic for triggering an audio stimulus when tracking velocity reaches a certain
    threshold.
    """

    def __init__(self, shared_state, speed_threshold=0.009, num_frames_mean=25):

        # Call the base class constructor
        super(ThresholdCallback, self).__init__(shared_state=shared_state)

        self.speed_threshold = speed_threshold
        self.num_frames_mean = num_frames_mean

    def setup_callback(self):

        print('setup')
        self.video_server = VideoServer(flyvr_shared_state=self.state)
        self.video_client = self.video_server.start_stream(frames_per_buffer=128, suggested_output_latency=0.002)
        print('done')

        # Setup the audio server for playback of sound
        self.sound_server = SoundServer(flyvr_shared_state=self.state)
        self.sound_client = self.sound_server.start_stream(frames_per_buffer=128, suggested_output_latency=0.002)

        self.stim = SinStim(frequency=250, amplitude=1, phase=0.0, sample_rate=44100, duration=10000)
        #self.stim = SquareWaveStim(frequency=100, duty_cycle=0.5, amplitude=1, sample_rate=44100, duration=1000)
        #self.stim = ConstantSignal(constant=-1, num_samples=10000)

        # Our buffer of past speeds
        self.speed_history = deque(maxlen=self.num_frames_mean)

        self.is_signal_on = False


    def process_callback(self, track_state):

        speed = abs(track_state.del_rot_cam_vec[1])
        #speed = track_state.speed

        # Add the speed to our history
        self.speed_history.append(speed)

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
