import mmap
import ctypes

import numpy as np

# The number of FicTrac fields in the output file
NUM_FICTRAC_FIELDS = 23


class SHMEMFicTracState(ctypes.Structure):
    """
    This class represents the FicTrac tracking state. These are the exact same values written to the output log file
    when FicTrac is run. Please consult the FicTrac user documentation for their meaning.
    """
    _fields_ = [
        ('frame_cnt', ctypes.c_int),
        ('del_rot_cam_vec', ctypes.c_double * 3),
        ('del_rot_error', ctypes.c_double),
        ('del_rot_lab_vec', ctypes.c_double * 3),
        ('abs_ori_cam_vec', ctypes.c_double * 3),
        ('abs_ori_lab_vec', ctypes.c_double * 3),
        ('posx', ctypes.c_double),
        ('posy', ctypes.c_double),
        ('heading', ctypes.c_double),
        ('direction', ctypes.c_double),
        ('speed', ctypes.c_double),
        ('intx', ctypes.c_double),
        ('inty', ctypes.c_double),
        ('timestamp', ctypes.c_double),
        ('seq_num', ctypes.c_int),
    ]


def fictrac_state_to_vec(s):
    return np.array([s.frame_cnt,
                     s.del_rot_cam_vec[0],
                     s.del_rot_cam_vec[1],
                     s.del_rot_cam_vec[2],
                     s.del_rot_error,
                     s.del_rot_lab_vec[0],
                     s.del_rot_lab_vec[1],
                     s.del_rot_lab_vec[2],
                     s.abs_ori_cam_vec[0],
                     s.abs_ori_cam_vec[1],
                     s.abs_ori_cam_vec[2],
                     s.abs_ori_lab_vec[0],
                     s.abs_ori_lab_vec[1],
                     s.abs_ori_lab_vec[2],
                     s.posx,
                     s.posy,
                     s.heading,
                     s.direction,
                     s.speed,
                     s.intx,
                     s.inty,
                     s.timestamp,
                     s.seq_num
                     ])


class SHMEMFicTracSignals(ctypes.Structure):
    """
    This class gives a set of variables used to send signals to the FicTrac program.
    """
    _fields_ = [
        ('close_signal_var', ctypes.c_int)
    ]

    def send_close(self):
        self.close_signal_var = 1


def print_fictrac_state(data):
    state_string = ""
    for field_name, field_type in data._fields_:
        field = getattr(data, field_name)
        if (isinstance(field, float) | isinstance(field, int)):
            state_string = state_string + str(field) + "\t"
        else:
            state_string = state_string + str(field[0]) + "\t" + str(field[1]) + "\t" + str(field[2]) + "\t"

    print(state_string)


def new_mmap_shmem_buffer():
    buf = mmap.mmap(-1, ctypes.sizeof(SHMEMFicTracState), "FicTracStateSHMEM")
    # noinspection PyTypeChecker
    return SHMEMFicTracState.from_buffer(buf)


def new_mmap_signals_buffer():
    buf = mmap.mmap(-1, ctypes.sizeof(ctypes.c_int32), "FicTracStateSHMEM_SIGNALS")
    # noinspection PyTypeChecker
    return SHMEMFicTracSignals.from_buffer(buf)
