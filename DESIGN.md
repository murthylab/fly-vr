# The Design of FlyVR and VR Experiments

FlyVR is a software for multi-sensory VR experiments on flies. The architecture of the software follows
the architecture of open- and closed-loop experiments themselves. There are a few different concepts
to understand.

1) the virtual 'world'
2) playlists
3) stimulus items in playlists
4) experiments

### the virtual world

At a high level a virtual reality is the ability to deliver stimuli to an observer and measure its response. Audio
stimuli are delivered to the fly using a speaker. Visual stimuli are shown on a projection screen, and optogenetic
stimuli are delivered by laser activation (using a DAQ). The response is the behaviour of the fly (its walking movement
on a tracked sphere) and its neural activity (measured using an external 2P microscope).

Open-loop experiments are broadly; the delivery of stimuli independent of the measured response of the fly.
Closed-loop experiments are broadly; the delivery of stimuli dependent upon, or in response to, behaviour of the
fly.

### playlists and stimulus items

Playlists are separated into the different stimulus modalities; audio, video, and daq (optogenetics). Each playlist
defines the stimuli to be given on that modality. For example, audio playlists include a list of audio
stimulus items (such as simple tones, or complicated melodies defined in matlab/numpy), video playlists include
types of visual stimuli (looming, gratings, etc), and optogenetic stimuli are different excitation pulsetrains.

### experiments

Experiments are the embodiment or description of how stimulus items are shown to the fly. An open-loop experiment
is a list of stimulus items to be shown in order. A closed-loop experiment is a list of stimulus items to be shown
and also a description of when they should be shown - depending on the fly behaviour (currently, its measured motion
on the tracked sphere)

## The Architecture of FlyVR

What follows is an approximate description of the architecture of FlyVR, to help best understand how to test
and develop experiments and stimuli. A more technical description is available in the [readme](README.md).

FlyVR is a number of individual programs. Those programs relevant to this high level discussion are the
programs that display/deliver stimuli, and the programs which control the progression of these stimulus items.
These programs communicate with oneanother to coordinate the delivery of stimuli to the fly.

* `flyvr-video.exe` - reads video playlists and displays visual stimulus items on a screen
* `flyvr-audio.exe` - reads audio playlists and plays audio stimulus items via the PC soundcard
* `flyvr-daq.exe` - reads daq playlists and generates pulsetrains for optogenetic stimulus
* `flyvr-experiment.ext` - allows testing more complicated closed-loop experiment logic

 This means to test your visual or audio stimulus and close-loop experiment logic you need to run the two
 programs `flyvr-XXX.exe` (where XXX is audio,video,daq depending on what you are testing), and `flyvr-experiment.exe`.

## Examples

I will now build from a simple audio-only open-loop experiment, to a more complicated multi-sensory closed
loop experiment. Note:

1. abridged config files are shown below, the full file is linked
2. in real operation flyvr also needs some device/assay specific configuration which is not provided, however
   most of the examples can be run against a previously recorded FicTrac tracking session aka
   a 'replay experiment'. If you do not have a DAQ you can simulate one and otherwise follow along
   below in most cases. See the [developing section in the README](README.md#Developing) for more
   information

#### A simple open-loop audio experiment

In this experiment we will simply play two audio signals to the fly continuously ([full config file](playlists/audio1.yml))

```yaml
playlist:
  audio:
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800, amplitude: 1.0}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400, amplitude: 1.0}
```

A Flyvr experiment can then be launched using `flyvr.exe -c playlists/audio1.yml`, or for testing only the
audio on your soundcard  `flyvr-audio.exe -c playlists/audio1.yml`

#### A simple video only VR experiment.

As above, but showing only two simple visual stimuli. ([full config file](playlists/video1.yml))

```yaml
playlist:
  video:
    - v_loom_stim: {name: 'looming'}
    - v_move_sq: {name: 'moving_square'}
```

A Flyvr experiment can then be launched using `flyvr.exe -c playlists/video1.yml`, or for testing only the
audio on your soundcard  `flyvr-video.exe -c playlists/video1.yml`

#### A simple video and audio experiment (the wrong way).

In this experiment we simply play both stimuli in loops repeatedly. As written, and practically, this is not
how this *type* of experiment should be implemented because of inherit imprecision in free-running looping
of stimulus items on different backends.

```yaml
playlist:
  audio:
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800, amplitude: 1.0}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400, amplitude: 1.0}
  video:
    - v_loom_stim: {name: 'looming'}
    - v_move_sq: {name: 'moving_square'}
```

#### A simple video and audio experiment (the CORRECT way).

To synchronize multiple stimuli across different modalities (such as video and audio) one should write an
experiment file. An experiment file is written in `.yaml` or python and describes when different stimulus
items should be played.

If you require different stimuli on different backends be started at the same time, you should write
a 'timed' experiment. The experiment `.yaml` supports this concept via the syntax below

```yaml
playlist:
  audio:
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800, amplitude: 1.0}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400, amplitude: 1.0}
  video:
    - v_loom_stim: {name: 'looming'}
    - v_move_sq: {name: 'moving_square'}
time:
  10000:
    do:
      - playlist_item: {backend: 'audio', identifier: 'sin800hz'}
      - playlist_item: {backend: 'video', identifier: 'v_loom_stim'}
  40000:
    do:
      - playlist_item: {backend: 'audio', identifier: 'sin400hz'}
      - playlist_item: {backend: 'video', identifier: 'v_move_sq'}
```

This says

* after 10000ms play the previously defined audio stimulus item 'sin800hz' and video stimulus item 'v_loom_stim'  
  (both start playing at the same time)
* after 40000ms play the previously defined audio stimulus item 'sin400hz' and video stimulus item 'v_move_sq'  
  (both start playing at the same time)

This can be launched using `flyvr.exe -c experiments/timed_switch_audio1_video1.yml`

#### A more complicated open-loop video and audio experiment

For ultimate flexibility experiment logic can be implemented in python. This allows true closed loop
experiments (such as playing stimuli in response to behaviour). It also allows more complicated open-loop
experiments.

In this experiment, every 5 seconds we randomly switch on and between different combinations of the previously defined
audio and video stimuli.

```yaml
playlist:
  audio:
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800, amplitude: 1.0}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400, amplitude: 1.0}
  video:
    - v_loom_stim: {name: 'looming'}
    - v_move_sq: {name: 'moving_square'}
```

The experiment logic is written in python thus

```python
import time
import random

from flyvr.control.experiment import Experiment


class _MyExperiment(Experiment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._t = time.time()

    def process_state(self, state):
        dt = time.time() - self._t
        if dt > 5:
            vstim = random.choice(('v_loom_stim', 'v_move_sq'))
            astim = random.choice(('sin800hz', 'sin800hz'))
            self.play_playlist_item(Experiment.BACKEND_VIDEO, vstim)
            self.play_playlist_item(Experiment.BACKEND_AUDIO, astim)
            self._t = time.time()

experiment = _MyExperiment()
```

Exploiting the ability to define the experiment logic in python, flyvr is now
launched `flyvr.exe -c playlist.yaml -e experiment.py`

## Testing a FlyVR Rig Using OL/CL Experiments

Following on from the
[non-OL timed video and audio experiment above](#a-more-complicated-open-loop-video-and-audio-experiment),
here are some suggested validation experiments to test FlyVR rigs and to further
exemplify concepts key to FlyVR.

#### A dynamic paired-random audio+optogenetic experiment

Imagine you have an experiment where you have several audio and optogenetic
stimuli defined and you want to randomly show only certain combinations of
audio and optogenetic at the same time. For example, if the daq playlist as items with
identifiers 'd1', 'd2', 'd3', and 'd4', and the audio playlist has items
with identifiers 'a1', 'a2', and 'a3', then we want to randomly choose to play
play simultaneously only (`d1' and 'a1'), ('d2' and 'a2'), or
('d3' and 'a3') and _not_ ('d2' and 'a1') for example.

This example is provided in the form of a [playlist](playlists/audio_daq_paused.yml) and
an [experiment](experiments/paired_random_audio_daq.py) for your study.

Please note the following configuration choices made in the playlist and suggested
to be included in the configuration file for the rig used

* both playlists are configured with `_options` `{random_mode: 'none', paused: true}`
  which indicates that when FlyVR has finished starting, nothing should independently
  start playing on each backend
* the experiment uses the `self.configured_playlist_items` attribute which lists the
  identifiers of all playlists items for all backends. This means in this hypothetical
  experiment the list of playlist items does not need to be duplicated in the
  experiment
* the experiment makes use of `self.is_started()` and
  `self.is_backend_ready(...)` to wait until FlyVR is started and all backends are
  ready before starting the first pair of stimuli playing
* note that if you are using scanimage to also record 2P images then you should set
  `remote_2P_next_disable` and simply record one stack (that you can break into smaller files by limiting
  the number YY if "Frames Done XX of YY"" in scanimage) for the entire experiment. This is because 
  FlyVR otherwise generates a new scaminage next-signal every time a new playlist item is played on
  any backend, thus the simultaneous starting of two stimuli on both backends will generate two stacks.


#### An example closed-loop randomized audio+optogenetic experiment

This example uses the same stimuli as the last experiment but instead of randomly
switching corresponding-pairs of audio+daq playlist items every number of seconds,
in this experiment we instead play a random audio and optogenetic stimulus every time
the fly (ball) speed exceeds a threshold value.

You should note that this experiment uses the same [playlist](playlists/audio_daq_paused.yml)
as [the previous](#a-dynamic-paired-random-audiooptogenetic-experiment), but a different
[experiment](experiments/cl_random_audio_daq.py).

#### Testing Closed Loop Experiments

Extending on the previous experiment where the fly (ball) speed was used to trigger a closed
loop response, it is possible to use a stepper motor which rotates the ball to test the
experiment logic and aspects of the system latency or synchronicity.

Pre-requisites: 
1) a stepper motor should be attached to the ball and connected to a phidgets
   stepper motor controller
2) the stepper motor controller is connected to port 0 on the phidget
3) FicTrac is calibrated
4) The _Phidgets Network Server_ is enabled and started ([instructions here](https://www.phidgets.com/docs/Phidget_Control_Panel#Network_Server_Tab), note status bar at bottom)  
   In 'normal' operation (which is lowest latency) the Phidget device is opened
   and controlled only by FlyVR (because it is used to signal scanimage).
   However, in this case, we need to also use the Phidget device to control the
   stepper motor.

First test the Phidget, stepper motor, and network server configration you should run
the ball controller alone (without FlyVR running). You can do this by
`$ python tests\ball_control_phidget\ball_control.py` which will randomly spin the ball
at two speeds in either direction (or stop it). If the ball reliably spins in both directions
and does not get stuck, then you can proceed to test the speed trigger.

The sample [experiment](experiments/cl_random_audio_daq.py) triggers when an empirically
determined speed threshold is exceeded. This value `SPEED_THRESHOLD` might need to be changed
to correspond to a true fly, or likely also to your ball+stepper mounting. To simply play
with the value, you can run only FicTrac and a very
[similar experiment](experiments/print_ball_speed.py) which just prints
when the threshold is exceeded. To do this perform the following

1. Launch FicTrac  
   `$ flyvr-fictrac -f FicTracPGR_ConfigMaster.txt -m log.txt`  
   where `-f FicTracPGR_ConfigMaster.txt` is the same value you would use in
   a 'real' FlyVR experiment configuration yaml
2. Launch the 'experiment'  
   `$ flyvr-experiment.exe -e experiments\print_ball_speed.py`  
   which will print every time the `SPEED_THRESHOLD` is exceeded. you can/should
   simply modify this experiment to determine your `SPEED_THRESHOLD` and `FILTER_LEN`
   values
3. Set the ball to different speeds  
   `$ python tests\ball_control_phidget\ball_control.py 123`  
   where 123 can be replaced with other values (max 3000) to spin the ball faster

Once you have determine the values you wish to use, you can launch the CL experiment, and
instead of needing a real fly, you can manually spin the ball using `ball_control.py` to
trigger the closed loop condition.

**Important**: Because the phidget is being operated in Network mode by the ball controller,
an additional configuration option must be added to your FlyVR config for this test or provided
on the command line `--phidget_network`

Finally, to launch and test your closed loop experiment you can do
1. Launch FlyVR  
   `flyvr.exe --phidget_network -c your_rig.yml -p playlists/audio_daq_paused.yml -e experiments/cl_random_audio_daq.py`  
   as always, `your_reg.yml` should contain the necessary configuration options specific to
   your hardware
2. Manually trigger the CL condition to spinning the ball  
   `$ python tests\ball_control_phidget\ball_control.py 123`  
   where `123` was the empirically determined value which exceeds the `SPEED_THRESHOLD` you
   determined earlier.
   
Note and Future Extensions: A new experiment that controlled the ball itself also from
within the experiment (using the same API as in `ball_control.py`) could be written, which
would eliminate the need to launch the `ball_control.py` in a separate terminal.

## Stimuli Randomization and Repeat

Random and repeat modes are specified in the playlist for each backend, within a special 'playlist item'
called `_options: {}`. For example, if an audio playlist begins with the following

```yaml
playlist:
  audio:
    - _options: {random_mode: 'shuffle', repeat: 2, random_seed: 42}
```

This it uses a randomization strategy called 'shuffle', and all items in the playlist
are repeated 2 times. A random seed can also be optionally specified. The supported values
for `random_mode` are

* `none`  
  no randomization. items play in the order they are defined
* `shuffle`  
  items are shuffled once and then (when `repeat > 0`) repeat played in that order
* `shuffle_non_repeat`  
  items are shuffled after every time they are all played
* `random_walk`
  items are played in a random order - all stimuli are randomly walked through for a total
  of `n_stimuli * repeat` times
* `random_walk_non_consecutive`  
  as `random_walk` but it is prevented to play the same item consecutively

## FlyVR Software Architecture

#### inter-process communication

There are two modes of inter-process communication in flyvr. The fictrac tracking state is shared
from fictrac to all other processes via shared memory. It follows that the lowest d_latency/d_t data to synchronize
between all processes is the shared memory fictrac frame number. This is written into every process output
`.h5` file and should be the means by which data is combined.

The second mode of IPC is using ZMQ. There is a central concept of a playlist with items (that have identifiers). Each
backend (audio, video, etc) can read a playlist containing backend-specific stimulus items. IPC commands are then
used to command the backend to 'play' this playlist.
