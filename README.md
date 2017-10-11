# flyvr
Software for running a experimental virtual reality setup for flies. This project is a work in progress.
# Usage
```
usage: flyvr.py [-h] [-v] -c CONFIG [-p STIM_PLAYLIST] [-a ATTENUATION_FILE]
                [-i ANALOG_IN_CHANNELS] [-o ANALOG_OUT_CHANNELS]
                [-l RECORD_FILE] [-f FICTRAC_CONFIG] [-m FICTRAC_CONSOLE_OUT]
                [-k FICTRAC_CALLBACK] [-g] [-s]

Args that start with '--' (eg. -v) can also be set in a config file (specified
via -c). Config file syntax allows: key=value, flag=true, stuff=[a,b,c] (for
details, see syntax at https://goo.gl/R74nmi). If an arg is specified in more
than one place, then commandline values override config file values which
override defaults.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -c CONFIG, --config CONFIG
                        Path to a configuration file.
  -p STIM_PLAYLIST, --stim_playlist STIM_PLAYLIST
                        A playlist file of auditory stimuli
  -a ATTENUATION_FILE, --attenuation_file ATTENUATION_FILE
                        A file specifying the attenuation function
  -i ANALOG_IN_CHANNELS, --analog_in_channels ANALOG_IN_CHANNELS
                        A comma separated list of numbers specifying the input
                        channels record. Default channel is 0.
  -o ANALOG_OUT_CHANNELS, --analog_out_channels ANALOG_OUT_CHANNELS
                        A comma separated list of numbers specifying the
                        output channels. Default channel is 0.
  -l RECORD_FILE, --record_file RECORD_FILE
                        File that stores output recorded on requested input
                        channels. Default is file is Ymd_HM_daq.h5 where
                        Ymd_HM is current timestamp.
  -f FICTRAC_CONFIG, --fictrac_config FICTRAC_CONFIG
                        File that specifies FicTrac configuration information.
  -m FICTRAC_CONSOLE_OUT, --fictrac_console_out FICTRAC_CONSOLE_OUT
                        File to save FicTrac console output to.
  -k FICTRAC_CALLBACK, --fictrac_callback FICTRAC_CALLBACK
                        A callback function that will be called anytime
                        FicTrac updates its state. It must take two
                        parameters; the FicTrac state, and an IOTask object
                        for communicating with the daq.
  -g, --pgr_cam_enable  Enable Point Grey Camera support in FicTrac.
  -s                    Shuffle the playback of the playlist randomly.
```
