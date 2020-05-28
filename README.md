# flyvr

Software for running a experimental virtual reality setup for flies. This project is a work in progress.

# Usage
```
usage: flyvr [-h] -c CONFIG [-v] [-p STIM_PLAYLIST] [-a ATTENUATION_FILE]
             [-i ANALOG_IN_CHANNELS]
             [--digital_in_channels DIGITAL_IN_CHANNELS]
             [-o ANALOG_OUT_CHANNELS] [--addSyncOutput]
             [--visual_stimulus VISUAL_STIMULUS]
             [--screen_calibration SCREEN_CALIBRATION] [--use_RSE USE_RSE]
             [--remote_2P_enable]
             [--remote_start_2P_channel REMOTE_START_2P_CHANNEL]
             [--remote_stop_2P_channel REMOTE_STOP_2P_CHANNEL]
             [--remote_next_2P_channel REMOTE_NEXT_2P_CHANNEL]
             [-l RECORD_FILE] [-f FICTRAC_CONFIG] [-m FICTRAC_CONSOLE_OUT]
             [--fictrac_plot_state] [--pgr_cam_enable] [--shuffle]
             [--start_delay START_DELAY] [--callback CALLBACK]
             [--ball_control_enable]
             [--ball_control_channel BALL_CONTROL_CHANNEL]
             [--ball_control_periods BALL_CONTROL_PERIODS]
             [--ball_control_durations BALL_CONTROL_DURATIONS]
             [--ball_control_loop]

Args that start with '--' (eg. -p) can also be set in a config file (specified
via -c). Config file syntax allows: key=value, flag=true, stuff=[a,b,c] (for
details, see syntax at https://goo.gl/R74nmi). If an arg is specified in more
than one place, then commandline values override config file values which
override defaults.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to a configuration file.
  -v                    Verbose output
  -p STIM_PLAYLIST, --stim_playlist STIM_PLAYLIST
                        A playlist file of auditory stimuli
  -a ATTENUATION_FILE, --attenuation_file ATTENUATION_FILE
                        A file specifying the attenuation function
  -i ANALOG_IN_CHANNELS, --analog_in_channels ANALOG_IN_CHANNELS
                        A comma separated list of numbers specifying the input
                        channels record. Default channel is 0.
  --digital_in_channels DIGITAL_IN_CHANNELS
                        A comma separated list of channels specifying the
                        digital input channels record. Default is None.
  -o ANALOG_OUT_CHANNELS, --analog_out_channels ANALOG_OUT_CHANNELS
                        A comma separated list of numbers specifying the
                        output channels. Default none for no output
  --addSyncOutput       Send a 5V power signal to the last AO channel for
                        visual synchronization.
  --visual_stimulus VISUAL_STIMULUS
                        A pre-defined visual stimulus
  --screen_calibration SCREEN_CALIBRATION
                        Where to find the (pre-computed) screen calibration
                        file
  --use_RSE USE_RSE     Use RSE (as opposed to differential) denoising on AI
                        DAQ inputs
  --remote_2P_enable    Enable remote start, stop, and next file signaling the
                        2-Photon imaging.
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
  --fictrac_plot_state  Enable plotting of FicTrac state history.
  --pgr_cam_enable      Enable Point Grey Camera support in FicTrac.
  --shuffle             Shuffle the playback of the playlist randomly.
  --start_delay START_DELAY
                        Delay the start of playback and acquisition from
                        FicTrac tracking by this many seconds. The default is
                        0 seconds.
  --callback CALLBACK   Filename of Python code that contains implementaion of
                        FlyVRCallback class. Used to plugincustom control
                        logic for closed loop experiments.
  --ball_control_enable
                        Enable control signals for stepper motor controlling
                        ball motion. Used for testing of closed loop setup.
  --ball_control_channel BALL_CONTROL_CHANNEL
                        String with name of two bit digital channels to send
                        ball signal.
  --ball_control_periods BALL_CONTROL_PERIODS
                        A comma separated list of periods (in milliseconds)
                        describing how to construct the ball control signal.
  --ball_control_durations BALL_CONTROL_DURATIONS
                        A comma separated list of durations (in seconds) for
                        each period in the ball_control_periods parameter.
  --ball_control_loop   Whether the ball control signal should loop
                        idefinitely or not.
```

TLDR;

* `flyvr -c empty.config.py`

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
* NI-DAQmx Support for C

This also requires ASIO drivers for your audio device / soundcard. If you are not sure if you have dedicated ASIO
drivers for your audio device (and it is recommended that you do) you should install ASIO4ALL (http://www.asio4all.org/, tested with 2.14).
When installing, ensure you choose to install the 'Offline Control Panel'.

## flyvr

* Install Python 3.7.X
* Create a virtual environment
  `python -m venv`
* Activate the virtual environment and install dependencies
  `python -m pip install -r requirements.txt`
* Run the tests  
  `python -m pytest`

## fictrac

If you are using a Point Grey/FLIR camera, make sure the [FlyCapture SDK](https://www.flir.com/products/flycapture-sdk/) is installed. Copy FlyCapture2_C.dll from the Point Grey directory (it is in the bin folder - for instance, C:\Program Files\Point Grey Research\FlyCapture2\bin64) and place it in your FicTrac directory. If it is named FlyCapture2_C_v100.dll rename it. I have included this version in the fictrac_calibration folder of the repo for now.

For closed loop, or general purpose tracking, FicTrac needs to be installed. In order to do this, first download the pre-built binaries available [here](https://github.com/murthylab/fic-trac-win/releases).

For configuring FicTrac, a few files are needed:
1. A TIFF file used as a mask to remove non-ball areas, bright spots, etc (show examples). There is currently a matlab function that will help create this mask available in Im2P_CreateNewMask.m. But first need to capture a single frame to use as reference point!

Note that you probably want to reduce the resolution of the frame to minimize how much data needs to be passed around.

2. A configuration file. Currently in FicTracPGR_ConfigMaster.txt

3. A calibration file (??). Currently in calibration-transform.dat. If you do not use this transform file, a new one will be created by a user-guided process the first time you run FicTrac. If you want to update it, you can delete the file and try again.

4. To run FicTrac, run FicTrac FicTracPGR_ConfigMaster.txt or FicTrac-PGR FicTracPGR_ConfigMaster.txt (if you are using a Point Grey camera).


Question: how do I exit FicTrac??
How to calculate vfov: https://www.reddit.com/r/fictrac/comments/e71ida/how_to_get_the_right_vfov/