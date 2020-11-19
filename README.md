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


# Usage
```
usage: flyvr [-h] [-c CONFIG_FILE] [-v] [--attenuation_file ATTENUATION_FILE]
             [-e EXPERIMENT_FILE] [--analog_in_channels ANALOG_IN_CHANNELS]
             [--digital_in_channels DIGITAL_IN_CHANNELS]
             [--analog_out_channels ANALOG_OUT_CHANNELS]
             [--screen_calibration SCREEN_CALIBRATION]
             [--use_RSE]
             [--remote_2P_enable]
             [--remote_start_2P_channel REMOTE_START_2P_CHANNEL]
             [--remote_stop_2P_channel REMOTE_STOP_2P_CHANNEL]
             [--remote_next_2P_channel REMOTE_NEXT_2P_CHANNEL]
             [-l RECORD_FILE] [-f FICTRAC_CONFIG] [-m FICTRAC_CONSOLE_OUT]
             [--pgr_cam_disable] [--start_delay START_DELAY]

Args that start with '--' (eg. --attenuation_file) can also be set in a config
file (specified via -c). The config file uses YAML syntax and must represent a
YAML 'mapping' (for details, see http://learn.getgrav.org/advanced/yaml). If
an arg is specified in more than one place, then commandline values override
config file values which override defaults.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG_FILE, --config CONFIG_FILE
                        config file path
  -v                    Verbose output
  --attenuation_file ATTENUATION_FILE
                        A file specifying the attenuation function
  -e EXPERIMENT_FILE, --experiment_file EXPERIMENT_FILE
                        A file defining the experiment (can be a python file
                        or a .yaml)
  --analog_in_channels ANALOG_IN_CHANNELS
                        A comma separated list of numbers specifying the input
                        channels record.Default channel is 0.
  --digital_in_channels DIGITAL_IN_CHANNELS
                        A comma separated list of channels specifying the
                        digital input channels record.Default is None.
  --analog_out_channels ANALOG_OUT_CHANNELS
                        A comma separated list of numbers specifying the
                        output channels.Default none for no output
  --screen_calibration SCREEN_CALIBRATION
                        Where to find the (pre-computed) screen calibration
                        file
  --visual_stimulus VISUAL_STIMULUS
                        A pre-defined visual stimulus
  --use_RSE             Use RSE (as opposed to differential) denoising on AI
                        DAQ inputs
  --remote_2P_disable   Disable remote start, stop, and next file signaling
                        the 2-Photon imaging (if the phidget is not detected,
                        signalling is disabled with a warning).
  --remote_start_2P_channel REMOTE_START_2P_CHANNEL
                        The digital channel to send remote start signal for
                        2-photon imaging. Default = port0/line0
  --remote_stop_2P_channel REMOTE_STOP_2P_CHANNEL
                        The digital channel to send remote stop signal for
                        2-photon imaging. Default = port0/line1.
  --remote_next_2P_channel REMOTE_NEXT_2P_CHANNEL
                        The digital channel to send remote next file signal
                        for 2-photon imaging. Default = port0/line2.
  -l RECORD_FILE, --record_file RECORD_FILE
                        File that stores output recorded on requested input
                        channels. Default is file is Ymd_HM_daq.h5 where
                        Ymd_HM is current timestamp.
  -f FICTRAC_CONFIG, --fictrac_config FICTRAC_CONFIG
                        File that specifies FicTrac configuration information.
  -m FICTRAC_CONSOLE_OUT, --fictrac_console_out FICTRAC_CONSOLE_OUT
                        File to save FicTrac console output to.
  --pgr_cam_disable     Dnable Point Grey Camera support in FicTrac.
  --start_delay START_DELAY
                        Delay the start of playback and acquisition from
                        FicTrac tracking by this many seconds. The default is
                        0 seconds.
```

TLDR;

* `flyvr`

## Usage of Individual Utilities

* `$ flyvr-fictrac-plot`  
  show a realtime plot of fictrac state
* `$ flyvr-fictrac-replay`  
  replay fictrac data from a previously recorded experiment record_file

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
       
   Note that you probably want to reduce the resolution of the frame to minimize how much data needs to be passed around.

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

For autoconfiguration to work, the Lightcrafter software must be 'Disconnected' from the 
projector (or closed). 

If you wish to show the visual stimulus on the desktop monitor (skipping the potential delay trying
to configure a non-connected lightcrafter, you can pass `--disable-projector`.

# Updating FlyVR

* Update the source code  
  `git pull --ff-only origin master`
* Activate the conda or virtual environment
* Re-install  
  * `python -m pip install -e .` to install in development mode (recommended)
  * `python -m pip install --upgrade .` to install a release version
* Run the tests  
  `python -m pytest`

# flyvr-architecture

The flyvr is a multi-process application for multi-sensory virtual reality. The different processes are separated largely
by the sensory modality they target, for example there is a single process dedicated to video stimulus, one for
audio stimulus, etc. The *primary* separate processes are (more explanations follow)

* flyvr  
  main application launcher, launches all other processes internally. usually all that is needed to be run
* flyvr-audio  
  process which reads the audio playlist and plays audio signals via the soundcard. can also
  list available sound cards (`flyvr-audio --list-devices`)
* flyvr-video
  process which reads video playlist and displays video stimulus on an attached lightcrafter projector (if connected)
* flyvr-daq
  process which drives the NI DAQ for the purposes of
  * outputing the opto stimulus
  * recording the analog inputs
* flyvr-fictrac  
  process which launches the fictrac binary
  * `flyvr-fictrac -f FicTracPGR_ConfigMaster.txt -m log.txt`
* flyvr-hwio  
  device which drives the scanimage signaling and is available for future expansion for other stimulus (odor, etc).
  It also has a few additional options to aid visual debugging
  * `flyvr-hwio -debug_led 5`
    * `--debug_led`  
      port on which to flash an LED upon starting a new playlist item

Similarly, the following secondary utilities are available also as separate processes to aid debugging, development, testing
or observing experiments in progress  

* flyvr-fictrac-replay  
  can replay a previously saved fictrac `.h5` file in order to test, for example, experiment logic or 
* flyvr-experiment  
  allows running flyvr experiments (`.yaml` or `.py`) in order to test their logic and progression. often used in conjunction with `flyvr-fictrac-replay`
* flyvr-print-state  
  prints the current flyvr state to the console
* flyvr-fictrac-plot
  shows an animated plot of the fictrac state (ball speed, direction, etc)
* flyvr-ipc-send  
  in internal utility for sending IPC messages to control other primary processes,
  e.g. (the complex escaping is necessary here in windows shell)
  * `flyvr-ipc-send.exe "{\"video_item\": {\"identifier\": \"v_loom_stim\"}}"`
  * `flyvr-ipc-send.exe "{\"audio_legacy\": \"sin\t10\t1\t0\t0\t0\t1\t650\"}"`
  * `flyvr-ipc-send.exe "{\"video_action\": \"play\"}"`
* flyvr-ipc-relay  
  (advanced only) internal message relay bus for start/stop/next-playlist-item messages

# credits

David Deutsch - Murthy lab, PNI, Princeton; Adam Calhoun - Murthy lab, PNI, Princeton; 
John Stowers - LoopBio, David Turner - PNI, Princeton

# license
Copyright (c) 2020 Princeton University
flyvr is released under a Clear BSD License and is intended for research/academic use only. 
For commercial use, please contact: Laurie Tzodikov (Assistant Director, Office of Technology Licensing), 
Princeton University, 609-258-7256.
