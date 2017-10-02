import ctypes
import sys

class SHMEMFicTracState(ctypes.Structure):
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

def print_fictrac_state(data):
    state_string = ""
    for field_name, field_type in data._fields_:
        field = getattr(data, field_name)
        if(isinstance(field, float) | isinstance(field, int)):
            state_string = state_string + str(field) + "\t"
        else:
            state_string = state_string + str(field[0]) + "\t" + str(field[1]) + "\t" + str(field[2]) + "\t"

    print state_string