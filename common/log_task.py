import h5py
import numpy as np
import sys

def log_audio_task_main(frame_queue, filename, num_channels=1, sizeincrement=100):

    f = h5py.File(filename, "w")

    dset_samples = f.create_dataset("samples", shape=[sizeincrement, num_channels],
                                    maxshape=[None, num_channels], dtype=np.float64)
    dset_systemtime = f.create_dataset("systemtime", shape=[sizeincrement, 1],
                                       maxshape=[None, 1], dtype=np.float64)
#    print("opened file \"{0}\".".format(filename))
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
