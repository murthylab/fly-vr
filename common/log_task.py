import h5py
import numpy as np
import sys

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
        elif isinstance(item, (np.ndarray, np.int64, np.float64, str, bytes)):
            h5file[path + key] = item
        elif isinstance(item, dict):
            recursively_save_dict_contents_to_group(h5file, path + key + '/', item)
        else:
            raise ValueError('Cannot save %s type'%type(item))

def log_audio_task_main(frame_queue, state, sizeincrement=100):

    # Get the output log file name from the options
    filename = state.options.record_file

    # Get the number of channels
    num_channels = len(state.options.analog_in_channels)

    # Open the HDF5 file for writing
    f = h5py.File(filename, "w")

    dset_samples = f.create_dataset("samples", shape=[sizeincrement, num_channels],
                                    maxshape=[None, num_channels], dtype=np.float64)
    dset_systemtime = f.create_dataset("systemtime", shape=[sizeincrement, 1],
                                       maxshape=[None, 1], dtype=np.float64)

    # Lets add options meta-data to samples dataset as attributes
    grp = f.create_group('options')
    recursively_save_dict_contents_to_group(grp, '/options/', state.options.__dict__)

    framecount = 0
    RUN = True
    while RUN:
        frame_systemtime = frame_queue.get()
        if framecount % sizeincrement == sizeincrement - 1:
            f.flush()
            dset_systemtime.resize(dset_systemtime.shape[
                                   0] + sizeincrement, axis=0)
        if frame_systemtime is None:
 #           print("   stopping save")
            RUN = False
        else:
 #           sys.stdout.write("\r   {:1.1f} seconds: saving {} ({})".format(
 #               frame_systemtime[1], frame_systemtime[0].shape, framecount))
            dset_samples.resize(dset_samples.shape[0] + frame_systemtime[0].shape[0], axis=0)
            dset_samples[-frame_systemtime[0].shape[0]:, :] = frame_systemtime[0]
            dset_systemtime[framecount, :] = frame_systemtime[1]
            framecount += 1
    f.flush()
    f.close()
#    print("   closed file \"{0}\".".format(filename))
