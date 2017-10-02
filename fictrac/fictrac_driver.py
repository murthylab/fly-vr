import shmem_transfer_data
import sys
import mmap
import ctypes


if __name__ == '__main__':
    # get
    shmem = mmap.mmap(-1, ctypes.sizeof(shmem_transfer_data.SHMEMFicTracState),
              "FicTracStateSHMEM")

    data = shmem_transfer_data.SHMEMFicTracState.from_buffer(shmem)
    shmem_transfer_data.print_fictrac_state(data)
    old_frame_count = data.frame_cnt
    while True:
        data = shmem_transfer_data.SHMEMFicTracState.from_buffer(shmem)
        new_frame_count = data.frame_cnt

        if old_frame_count < new_frame_count:
            shmem_transfer_data.print_fictrac_state(data)
            old_frame_count = new_frame_count