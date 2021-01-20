# FlyVR

FlyVR is a framework for the design and control of multisensory virtual reality systems for neuroscientists.
It is written in Python, with modular design that allows the control of open and closed loop experiments with 
one or more sensory modality. In its current implementation, FlyVR uses fictrac (see below) to track the path of a
fly walking on an air-suspended ball. A projector and a sound card are used for delivering visual and auditory stimuli,
and other analog outputs (through NI-DAQ or phidgets devices) control other stimuli such as optogenetic stimulation, or
triggers for synchronization (e.g., with ScanImage).

**FlyVR is currently under development. Please see below for credits and license info.** If you would like to
contribute to testing the code, please contact David Deutsch (ddeutsch@princeton.edu), postdoc in the
Murthy Lab @ the Princeton Neuroscience Institute.

* For a walk-through of FlyVR's design and what experiments are possible, see [Design](DESIGN.md)
* FlyVR's data format is described [here](https://docs.google.com/document/d/1NAuY08Yhk6uHVGp64p8_fauebuzAw_XVTo_fu1uZUH8/edit#heading=h.k1xci4u7fcsc) (wip)

# Usage
```
usage: flyvr [-h] [-c CONFIG_FILE] [-v] [--attenuation_file ATTENUATION_FILE]
             [-e EXPERIMENT_FILE] [-p PLAYLIST_FILE]
             [--screen_calibration SCREEN_CALIBRATION] [--use_RSE]
             [--remote_2P_disable]
             [--remote_start_2P_channel REMOTE_START_2P_CHANNEL]
             [--remote_stop_2P_channel REMOTE_STOP_2P_CHANNEL]
             [--remote_next_2P_channel REMOTE_NEXT_2P_CHANNEL]
             [--scanimage_next_start_delay SCANIMAGE_NEXT_START_DELAY]
             [--remote_2P_next_disable] [--phidget_network]
             [--keepalive_video] [--keepalive_audio] [-l RECORD_FILE]
             [-f FICTRAC_CONFIG] [-m FICTRAC_CONSOLE_OUT] [--pgr_cam_disable]
             [--wait] [--delay DELAY] [--projector_disable]
             [--samplerate_daq SAMPLERATE_DAQ] [--print-defaults]

Args that start with '--' (eg. -v) can also be set in a config file (specified
via -c). The config file uses YAML syntax and must represent a YAML 'mapping'
(for details, see http://learn.getgrav.org/advanced/yaml). If an arg is
specified in more than one place, then commandline values override config file
values which override defaults.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG_FILE, --config CONFIG_FILE
                        config file path
  -v, --verbose         Verbose output.
  --attenuation_file ATTENUATION_FILE
                        A file specifying the attenuation function.
  -e EXPERIMENT_FILE, --experiment_file EXPERIMENT_FILE
                        A file defining the experiment (can be a python file
                        or a .yaml).
  -p PLAYLIST_FILE, --playlist_file PLAYLIST_FILE
                        A file defining the playlist, replaces any playlist
                        defined in the main configuration file
  --screen_calibration SCREEN_CALIBRATION
                        Where to find the (pre-computed) screen calibration
                        file.
  --use_RSE             Use RSE (as opposed to differential) denoising on AI
                        DAQ inputs.
  --remote_2P_disable   Disable remote start, stop, and next file signaling
                        the 2-Photon imaging (if the phidget is not detected,
                        signalling is disabled with a warning).
  --remote_start_2P_channel REMOTE_START_2P_CHANNEL
                        The digital channel to send remote start signal for
                        2-photon imaging.
  --remote_stop_2P_channel REMOTE_STOP_2P_CHANNEL
                        The digital channel to send remote stop signal for
                        2-photon imaging.
  --remote_next_2P_channel REMOTE_NEXT_2P_CHANNEL
                        The digital channel to send remote next file signal
                        for 2-photon imaging.
  --scanimage_next_start_delay SCANIMAGE_NEXT_START_DELAY
                        The delay [ms] between next and start pulses when
                        signaling the 2-photon remote (<0 disables sending a
                        start after a next).
  --remote_2P_next_disable
                        Disable remote next (+start) signaling every stimulus
                        item. Just signal start and stop at the beginning and
                        end of an experiment.
  --phidget_network     connect to phidget over network protocol (required for
                        some motor-on-ball CL tests)
  --keepalive_video     Keep the video process running even if they initially
                        provided playlist contains no video items (such as if
                        you want to later play dynamic video items not
                        declared in the playlist).
  --keepalive_audio     Keep the audio process running even if they initially
                        provided playlist contains no audio items (such as if
                        you want to later play dynamic audio items not
                        declared in the playlist).
  -l RECORD_FILE, --record_file RECORD_FILE
                        File that stores output recorded on requested input
                        channels. Default is file is Ymd_HM_daq.h5 where
                        Ymd_HM is current timestamp.
  -f FICTRAC_CONFIG, --fictrac_config FICTRAC_CONFIG
                        File that specifies FicTrac configuration information.
  -m FICTRAC_CONSOLE_OUT, --fictrac_console_out FICTRAC_CONSOLE_OUT
                        File to save FicTrac console output to.
  --pgr_cam_disable     Disable Point Grey Camera support in FicTrac.
  --wait                Wait for start signal before proceeding (default false
                        in single process backends, and always true in the
                        main launcher).
  --delay DELAY         Delay main startup by this many seconds. Negative
                        number means wait forever.
  --projector_disable   Do not setup projector in video backend.
  --samplerate_daq SAMPLERATE_DAQ
                        DAQ sample rate (advanced option, do not change)
  --print-defaults      Print default config values
```

TLDR;

 * FlyVR reads its configuration from the command line and one or more files
   * `-c config.yml`  
     is the main configuration and *can* contain *both* the rig-specific configuration
     *and* the experiment playlist
      * Example rig configurations can be found in the `configs` directory.
   * `-p playlist.yml`  
     contains *only* the definition of the stimulus playlist. Any other configuration
     is ignored.
      * Sample playlists can be found in the `playlists` directory
 * By allowing separating the playlist and rig-specific configuration (such as how the
   DAQ is wired) one can use the same playlists on multiple rigs.
 * It is however not necessary to have *both* a `config.yml` and a `playlist.yml` - they
   can be combined into `config.yml` if desired
 * More information on the configuration possibilities can be found in the
   [configuration](#configuration) section

If you are developing a stimulus playlist (video example, substitute for audio as appropriate)

 * copy an example playlist e.g. copy 'playlists/video1.yml' to 'myvideo.yml'
 * exit, test and experiment on the playlist using the single launcher `flyvr-video.exe --config myvideo.yml`

When you have finished the playlist and experiment development and wish to run on a rig

* create a rig-specific config file (see templates in configs/) with the electrical connections
  `analog_in_channels`, `remote_start_2P_channel`, etc
* copy the rig-specific config template into a new config file for your experiment, 
  e.g. 'my_upstairs_video_experiment.yml', on this rig
* copy the contents of your tested 'myvideo.yml' playlists into 'my_upstairs_video_experiment.yml' 
* `flyvr --config my_upstairs_audio_experiment.yml`

When starting the `flyvr` program it will wait an additional `--delay` seconds, after all backends are
ready, before starting the experiment (playing the first item on all playlists). If `--delay` is
negative then `flyvr` will wait until the start button is pressed in the GUI.


# Installation

You need to be running an up-to-date Windows 10 installation.

This requires a NI DAQ (PCI-X series). To begin, install NI-DAQmx 19.6.X (from https://www.ni.com/en-us/support/downloads/drivers/download.ni-daqmx.html#333268).
The NI-DAQmx installer offers a number of options. You must install at least the following components
* NI-DAQmx driver
* NI Measurement and Automation Explorer 'NI MAX'
  * sometimes called 'NI Runtime with Configuration Support' (MAX) if using the  
    lightweight web installer
* NI-DAQmx Support for C

This also requires ASIO drivers for your audio device / soundcard. If you are not sure if you have dedicated ASIO
drivers for your audio device (and it is recommended that you do) you should install ASIO4ALL (http://www.asio4all.org/, tested with 2.14).
When installing, ensure you choose to install the 'Offline Control Panel'.

Finally, it also requires Phidgets drivers for the arbitrary IO and scanimage support. On windows you should also
install 
* [Phidget Control Panel (64-bit installer)](https://www.phidgets.com/docs/OS_-_Windows)
* Network Phidget Support (optional)  
  Note: On Windows 10 you might already have the required libraries. You can determine this by switching to the network
  tab in the Phidgets control panel. If it is not available, you must install
  [bonjour print service](https://support.apple.com/kb/DL999?locale=en_US). If it is available, you do not need
  to do anything further

## flyvr

(note, these installation instructions assume using the 'official' python.org python and built-in
virtual environments, NOT conda/miniconda. If you wish to use conda/miniconda then you will
need to use conda specific commands to create and activate the conda environment)

* Install Python 3.7.X
* Create a virtual environment (in checkout dir, named env)
  `C:\Path\To\python.exe -m venv env`  
  * if you installed python only to your user, the path is
    `"C:\Users\XXX\AppData\Local\Programs\Python\Python37\python.exe"`
* Activate the virtual environment  
  `venv\Scrips\activate.bat`
* ensure python packaging and built utilities are up to date  
  `python -m pip install -U pip setuptools wheel`
* install dependencies  
  `python -m pip install -r requirements.txt`
* Install flyvr
  * `python -m pip install -e .` to install in development mode (recommended)
  * `python -m pip install .` to install a release version
* Run the tests  
  `python -m pytest`
  * Note: by default, the tests will attempt to test the DAQ and soundcard. If you are running the tests
    on a computer without this hardware, or you wish to simply develop experimental logic or visual stimuli
    then you can skip these tests using  
    * `python -m pytest -m "not (use_soundcard or use_daq)"`  
      (skips both DAQ AND soundcard tests)
    * `python -m pytest -m "not use_daq"`  
      (skips DAQ tests)

## fictrac

If you are using a Point Grey/FLIR camera, make sure the [FlyCapture SDK](https://www.flir.com/products/flycapture-sdk/) is installed.
Copy FlyCapture2_C.dll from the Point Grey directory (it is in the bin folder - for instance,
`C:\Program Files\Point Grey Research\FlyCapture2\bin64`) and place it in your FicTrac directory. If it is named
`FlyCapture2_C_v100.dll` rename it. I have included this version in the fictrac_calibration folder of the repo for now.

For closed loop, or general purpose tracking, FicTrac needs to be installed. In order to do this, first download
the pre-built binaries available [here (private bucket)](https://bucket.pni.princeton.edu/murthy/FicTrac).
Please always download this file as you might have an identically named old version.

For configuring FicTrac, a few files are needed:

1. A TIFF file used as a mask to remove non-ball areas, bright spots, etc (show examples).
   There is currently a MATLAB function that will help create this mask available in `Im2P_CreateNewMask.m`. But
   first need to capture a single frame to use as reference point!  
   Note that you probably want to reduce the resolution of the frame to minimize how much data needs to
   be passed around.

2. A configuration file. Currently in FicTracPGR_ConfigMaster.txt

3. A calibration file (??). Currently in `calibration-transform.dat`. If you do not use this transform file,
   a new one will be created by a user-guided process the first time you run FicTrac. If you want to update it,
   you can delete the file and try again.

4. To run FicTrac, run `FicTrac FicTracPGR_ConfigMaster.txt` or `FicTrac-PGR FicTracPGR_ConfigMaster.txt`
   (if you are using a Point Grey camera).

## lightcrafter DLP (for visual stimulus)

Flyvr, and the `flyvr-video.exe` binary by default attempt to automatically configure and show
the visual stimulus on a DLP lightcrafter configured in the appropriate mode. This assumes that
the lightcrafter software has been installed, and that the lightcrafter is connected, powered on,
and on the default 192.168.1.100 IP address.

For auto-configuration to work, the Lightcrafter software must be 'Disconnected' from the 
projector (or closed). 

If you wish to show the visual stimulus on the desktop monitor (skipping the potential delay trying
to configure a non-connected lightcrafter, you can pass `--projector_disable`.

# Updating FlyVR

* Update the source code  
  `git pull --ff-only origin master`
* Activate the conda or virtual environment
* Re-install  
  * `python -m pip install -e .` to install in development mode (recommended)
  * `python -m pip install --upgrade .` to install a release version
* Run the tests  
  `python -m pytest`

# FlyVR Architecture

The flyvr is a multi-process application for multi-sensory virtual reality. The different processes are separated largely
by the sensory modality they target, for example there is a single process dedicated to video stimulus, one for
audio stimulus, etc. The *primary* separate processes are (more explanations follow)

* `flyvr`  
  main application launcher, launches all other processes internally. usually all that is needed to be run
* `flyvr-audio`  
  process which reads the audio playlist and plays audio signals via the soundcard. can also
  list available sound cards (`flyvr-audio --list-devices`).
  * you can also plot the audio playlist using `--plot` which will plot the audio timeseries  
    `flyvr-audio.exe --plot --config playlists\audio2.yml`
  * you can convert single-channel audio/daq playlists into the new format with `--convert-playlist` with the following
    caveats:
    * playlists should be first converted to single-channel format, so if it is a mixed or multiple channel v1
      playlist then you need to make it single channel for the backend (audio/daq) which you care about. I.e.
      compare 'tests/sample_data/v1/IPI36_16pulses_randomTiming_SC.txt' with
      'tests/sample_data/v1/IPI36_16pulses_randomTiming_SC_1channel.txt'. in the DAQ case, see
      'tests/test_data/nivedita_vr1/opto_nivamasan_10sON90sOFF.txt'
    * if the playlist was a complicated mixed audio/opto playlists then per the conversion requirement above,
      you will convert the input to two old v1 playlists, and call `--convert-playlist` twice
    * if your playlist included matlab stimuli then you should change the paths to the matlab mat files
      in the converted playlist. by default, if a relative path or only a filename is given, the path is
      relative to the playlist/config file
    * all converted playlists will be placed into an 'audio' playlist - this should be adapted to daq if the
      playlist is actually for the DAQ opto outputs
* `flyvr-video`  
  process which reads video playlist and displays video stimulus on an attached lightcrafter projector (if connected)
  (pass `--projector_disable` if you dont have a projector connected)
* `flyvr-daq`  
  process which drives the NI DAQ for the purposes of
  * outputing the opto stimulus
  * recording the analog inputs
* `flyvr-fictrac`  
  process which launches the fictrac binary
  * `flyvr-fictrac -f FicTracPGR_ConfigMaster.txt -m log.txt`
* `flyvr-hwio`  
  device which drives the scanimage signaling and is available for future expansion for other stimulus (odor, etc).
  It also has a few additional options to aid visual debugging
  * `flyvr-hwio -debug_led 5`
    * `--debug_led`  
      port on which to flash an LED upon starting a new playlist item

Similarly, the following secondary utilities are available also as separate processes to aid debugging, development, testing
or observing experiments in progress
* `flyvr-fictrac-replay`  
  can replay a previously saved fictrac `.h5` file in order to test, for example, experiment logic or 
* `flyvr-experiment`  
  allows running flyvr experiments (`.yaml` or `.py`) in order to test their logic and progression. 
  often used in conjunction with `flyvr-fictrac-replay`
* `flyvr-gui`  
  launches the standalone GUI which shows FlyVR state (frame numbers, sample numbers, etc)
* `flyvr-print-state`  
  prints the current flyvr state to the console
* `flyvr-fictrac-plot`  
  shows an animated plot of the fictrac state (ball speed, direction, etc)
* `flyvr-ipc-send`  
  in internal utility for sending IPC messages to control other primary processes,
  e.g. (the complex escaping is necessary here in windows shell)
  * `flyvr-ipc-send.exe "{\"video_item\": {\"identifier\": \"v_loom_stim\"}}"`
  * `flyvr-ipc-send.exe "{\"audio_legacy\": \"sin\t10\t1\t0\t0\t0\t1\t650\"}"`
  * `flyvr-ipc-send.exe "{\"video_action\": \"play\"}"`
* `flyvr-ipc-relay`  
  (advanced only) internal message relay bus for start/stop/next-playlist-item messages

# Configuration

Configuration for FlyVR is done via a YAML format configuration file that is passed on the command
line via the `--config` or `-c` argument. As explained in [design](DESIGN.md), a FlyVR experiment
contains two (three really, including a closed loop experiment definition) types of configuration
information:
 * FlyVR configuration (under the `configuration` section in the yaml file)
 * Stimulus playlists (under the `playlist` section)
 * An optional closed-loop experiment definition (under the `experiment` section)

Note 1: most configuration parameters can be supplied also on the command line, and these
        override values specified in the configuration section

Note 2: playlist and experiment configuration can be stored in separate configuration files and
        be supplied on the command line via the `-p` or `--playlist_file` and `-e` or `--experiment_file`
        arguments

The following configuration can only be defined in the `configuration` section of the yaml file and
can not be supplied on the command line
 * `analog_in_channels`  
   a mapping/dictionary of DAQ channel number to description, e.g. `{2: 'temperature'}` defines an analog
   input on `AI2` called 'temperature'
 * `analog_out_channels`  
   as above, but can only contain one channel. The channel to which the optogenetic stimulus is driven from 

After every experiment, the total configuration is saved in a `YYYYMMDD_HHMM.config.yml` file alongside the
other output files. The is an 'all-in-one' configuration where both the configuration *and* any additional
`-p playlist.yml` or `-e experiment.yml` information is included in the one file. 

### default values

The default values of all configuration parameters can be displayed by running any application with
`--print-defaults`.

Note: If you want to know the final value of all configuration variables as would have been used
in a FlyVR experiment, you can pass `--print-defaults --verbose`. This will print the combined configuration,
playlist, and closed-loop experiment (if defined in the yaml meta-language).


# Developing

* If you can reproduce an issue using the single issue launchers then please try to do so
* Run everything with verbose `-v` arguments for more debugging information
* It can be convenient to replay old h5 files of fictrac data for testing. With the individual
  utilities you must run `flyvr-fictrac-replay` but within your normal config file you can
  also run with the follwing in your yaml config  
  `fictrac_config: 'C:/path/to/fictrac/config/180719_103_output.h5'`
* If you do not have DAQ hardware you can create a simulated device which will allow you to
  otherwise use the rest of the software
  * Open NI Max, Right-click 'Devices and Interfaces', create a 
  'Simulated NI-DAQmx device or instrument', select 'NI PCIe-6353' as the simulated
  device type.

# Credits

David Deutsch - Murthy lab, PNI, Princeton; Adam Calhoun - Murthy lab, PNI, Princeton; 
John Stowers - [LoopBio](http://loopbio.com/consulting/), David Turner - PNI, Princeton

# License
Copyright (c) 2020 Princeton University
flyvr is released under a Clear BSD License and is intended for research/academic use only. 
For commercial use, please contact: Laurie Tzodikov (Assistant Director, Office of Technology Licensing), 
Princeton University, 609-258-7256.
