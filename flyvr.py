import time
from multiprocessing import freeze_support

from audio import io_task
from common.concurrent_task import ConcurrentTask

savefilename = time.strftime('data/Y%m%d_%H%M_')

if __name__ == '__main__':
    freeze_support()
    print("DAQ Init")
    daqTask = ConcurrentTask(task=io_task.audio_output_task_main, comms="pipe", taskinitargs=[])
    daqTask.start()

    time.sleep(2)
    daqTask.send("START")
    time.sleep(10)
    daqTask.send("STOP")
    time.sleep(2)
    daqTask.close()