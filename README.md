# flyvr
Software for running a experimental virtual reality setup for flies. This project is a work in progress.
# Usage
```
Usage: flyvr.py [options]

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -p STIM_PLAYLIST, --stim_playlist=STIM_PLAYLIST
                        A playlist file of auditory stimuli
  -a ATTENUATION_FILE, --attenuation_file=ATTENUATION_FILE
                        A file specifying the attenuation function
  -i ANALOG_IN_CHANNELS, --analog_in_channels=ANALOG_IN_CHANNELS
                        A comma separated list of numbers specifying the input
                        channels record. Default channel is 0.
  -o ANALOG_OUT_CHANNELS, --analog_out_channels=ANALOG_OUT_CHANNELS
                        A comma separated list of numbers specifying the
                        output channels. Default channel is 0.
  -d DISPLAY_INPUT_CHANNEL, --display_input_channel=DISPLAY_INPUT_CHANNEL
                        Input channel to display in realtime. Default is
                        channel 0.
  -l RECORD_FILE, --record_file=RECORD_FILE
                        File that stores output recorded on requested input
                        channels. Default is file is Y%m%d_%H%M_daq.h5 where
                        Y%m%d_%H%M is current timestamp.
  -s                    Shuffle the playback of the playlist randomly.
```
