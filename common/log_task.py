import h5py
import numpy as np
import sys

from audio.signal_producer import SignalProducer, SignalNextEventData
from audio.stimuli import AudioStimPlaylist


def recursively_save_dict_contents_to_group(h5file, path, dic):
    """
    Saves dictionary to an HDF5 files, calls itself recursively if items in
    dictionary are not np.ndarray, np.int64, np.float64, str, bytes. Objects
    must be iterable.
    """
    for key, item in dic.items():
        if item is None:
            h5file[path + key] = ""
        elif isinstance(item, bool):
            h5file[path + key] = int(item)
        elif isinstance(item, list):
            h5file[path + key] = np.asarray(item)
        elif isinstance(item, (np.ndarray, np.int64, np.float64, str, bytes, float)):
            h5file[path + key] = item
        elif isinstance(item, dict):
            recursively_save_dict_contents_to_group(h5file, path + key + '/', item)
        else:
            raise ValueError('Cannot save %s type'%type(item))


def make_event_metadata_dtype(metadata):
    type_desc = []
    for field_name in metadata:
        value = metadata[field_name]
        type_desc.append( (field_name, type(value)) )

def log_audio_task_main(frame_queue, state, sizeincrement=100, out_hist_size_increment=1000):

    # Get the output log file name from the options
    filename = state.options.record_file

    # Get the number of channels
    num_in_channels = len(state.options.analog_in_channels)
    num_out_channels = len(state.options.analog_out_channels)

    # For each output channel, keep track of number of samples generated.
    num_samples_out = [0 for i in xrange(num_out_channels)]

    # Open the HDF5 file for writing
    f = h5py.File(filename, "w")

    input_grp = f.create_group("input")
    dset_samples = input_grp.create_dataset("samples", shape=[sizeincrement, num_in_channels],
                                    maxshape=[None, num_in_channels],
                                    chunks=(sizeincrement, num_in_channels),
                                    dtype=np.float64, scaleoffset=8)
    dset_systemtime = input_grp.create_dataset("systemtime", shape=[sizeincrement, 1],
                                       maxshape=[None, 1], dtype=np.float64)

    # Lets add options meta-data to samples dataset as attributes
    options_grp = f.create_group('options')
    recursively_save_dict_contents_to_group(options_grp, '/options/', state.options.__dict__)

    # The output group will contain event data about samples written to the DAQ.
    output_grp = f.create_group('output')

    # The output group will contain event data about samples written to the DAQ.
    fictrac_grp = f.create_group('fictrac')

    # Add a group for each output channel
    channel_grps = [output_grp.create_group("ao" + str(channel)) for channel in state.options.analog_out_channels]

    # Add a producer group, this will hold unique instances of signal producers
    prod_grps = [channel_grp.create_group("producers") for channel_grp in channel_grps]

    # Add a history dataset that records occurrences of events
    hist_dsets = [channel_grps[i].create_dataset("history", shape=[out_hist_size_increment, 2],
                                               maxshape=[None, 2], dtype=np.int64)
                  for i in xrange(num_out_channels)]

    # Keep track of the current index for each channels events
    hist_indices = [0 for i in xrange(num_out_channels)]

    # Create a dataset for fictrac history
    fictrac_size_increment = 10000
    fictrac_curr_idx = 0
    fictrac_dset = fictrac_grp.create_dataset("frames_samples", shape=[fictrac_size_increment, 2],
                               maxshape=[None, 2], dtype=np.int64)

    # A dictionary that stores data generation events we have received. We just want to keep track of unique
    # events.
    data_generation_events = {}
    data_event_max_index = 0

    framecount = 0
    RUN = True
    playlist = None
    while RUN:

        # Get the message
        msg = frame_queue.get()

        # If we get a None msg, its a shutdown signal
        if msg is None:
            RUN = False
        # If it is tuple with a numpy array and a float then it is a frame ans system time message from aquisition
        elif isinstance(msg, tuple) and len(msg) == 2 and isinstance(msg[0], np.ndarray) and isinstance(msg[1], float):
            frame_systemtime = msg
            #sys.stdout.write("\r   {:1.1f} seconds: saving {} ({})".format(
                #frame_systemtime[1], frame_systemtime[0].shape, framecount))
            dset_samples.resize(dset_samples.shape[0] + frame_systemtime[0].shape[0], axis=0)
            dset_samples[-frame_systemtime[0].shape[0]:, :] = frame_systemtime[0]
            dset_systemtime[framecount, :] = frame_systemtime[1]
            framecount += 1

            # Resize the system time dataset if needed.
            if framecount % sizeincrement == sizeincrement - 1:
                f.flush()
                dset_systemtime.resize(dset_systemtime.shape[0] + sizeincrement, axis=0)
        elif isinstance(msg, SignalNextEventData):
            # Ok, check if this is a signal producer event. This means a signal generator's next method was called.

            # Get the channel that this output is occurring on
            channel = msg.channel

            # Get the history dataset for this channel
            dset = hist_dsets[channel]

            # Resize the channels events history dataset if needed
            if hist_indices[channel] % out_hist_size_increment == out_hist_size_increment - 1:
                f.flush()
                dset.resize(dset.shape[0] + out_hist_size_increment, axis=0)

            # Record the event in the table by adding its index and start sample number
            dset[hist_indices[channel], :] = [msg.producer_id, num_samples_out[channel]]
            hist_indices[channel] += 1

            num_samples_out[channel] += msg.num_samples
        elif isinstance(msg, tuple) and len(msg) == 2:

            fictrac_dset[fictrac_curr_idx, :] = [msg[0], msg[1]]
            fictrac_curr_idx += 1

            # Resize the dataset if needed.
            if fictrac_curr_idx % fictrac_size_increment == fictrac_size_increment - 1:
                f.flush()
                fictrac_dset.resize(fictrac_dset.shape[0] + fictrac_size_increment, axis=0)

        else:
            raise ValueError("Bad message sent to logging thread.")

    # Shrink the data sets if we didn't fill them up
    for i in xrange(num_out_channels):
        hist_dsets[i].resize(hist_indices[i], axis=0)

    fictrac_dset.resize(fictrac_curr_idx, axis=0)

    f.flush()
    f.close()
#    print("   closed file \"{0}\".".format(filename))
