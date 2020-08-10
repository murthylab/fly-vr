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
stimuli are delivered by laser activation. The response is the behaviour of the fly (its walking movement on a
tracked sphere) and its neural activity (measured using an external 2P microscope).

Open-loop experiments are broadly; the delivery of stimuli independent of the measured response of the fly.
Closed-loop experiments are broadly; the delivery of stimuli dependent upon, or in response to, behaviour of the
fly.

### playlists and stimulus items

Playlists are separated into the different stimulus modalities; audio, video, and optogenetics. Each playlist
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
2. flyvr also needs some device/assay specific configuration which is not provided

#### A simple open-loop audio experiment

In this experiment we will simply play two audio signals to the fly continuously ([full config file](playlists/audio1.yml))

```yaml
playlist:
  audio:
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400}
```

A Flyvr experiment can then be launched using `flyvr.exe -c playlists/audio1.yml`, or for testing only the
audio on your soundcard  `flyvr-audio.exe -c playlists/audio1.yml`

#### A simple video only VR experiment.

As above, but showing only two simple visual stimuli. ([full config file](playlists/audio1.yml))

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
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400}
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
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400}
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

This can be launched using `flyvr.exe -c experiments/timed_audio_video.yml`

#### A more complicated open-loop video and audio experiment

For ultimate flexibility experiment logic can be implemented in python. This allows true closed loop
experiments (such as playing stimuli in response to behaviour). It also allows more complicated open-loop
experiments.

In this experiment, every 5 seconds we randomly switch on and between different combinations of the previously defined
audio and video stimuli.

```yaml
playlist:
  audio:
    - sin800hz: {name: 'sin', duration: 1000, frequency: 800}
    - sin400hz: {name: 'sin', duration: 1000, frequency: 400}
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

## FlyVR Software Architecture

#### inter-process communication

There are two modes of inter-process communication in flyvr. The fictrac tracking state is shared
from fictrac to all other processes via shared memory. It follows that the lowest d_latency/d_t data to synchronize
between all processes is the shared memory fictrac frame number. This is written into every process output
`.h5` file and should be the means by which data is combined.

The second mode of IPC is using ZMQ. There is a central concept of a playlist with items (that have identifiers). Each
backend (audio, video, etc) can read a playlist containing backend-specific stimulus items. IPC commands are then
used to command the backend to 'play' this playlist.