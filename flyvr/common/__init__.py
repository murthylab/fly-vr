import sys
import traceback

from multiprocessing import Value


class SharedState(object):
    """
    A class to represent the shared state between our concurrent tasks. We can add values to this shared state and they
    will be passed as an argument to all tasks. This allows us to communicate with thread safe shared variables.
    """
    def __init__(self, options, logger):

        # Lets store the options passed to the program. This does not need to be stored in a thread
        # safe manner.
        self.options = options

        # Create a thread safe Value that specifies the current run state. This will allow
        # us to signal shutdown to multiple processes.
        self.RUN = Value('i', 1)

        # Create a thread safe Value to signal when the DAQ is aquiring samples.
        self.DAQ_READY = Value('i', 0)

        # A variable that communicates to the main DAQ thread to start playback and aquisition
        self.START_DAQ = Value('i', 0)

        # Thread safe Value to signal when FicTrac is running an processing frames.
        self.FICTRAC_READY = Value('i', 0)

        # Current FicTrac frame number
        self.FICTRAC_FRAME_NUM = Value('i', 0)

        # The total number of samples written to the DAQ
        self.DAQ_OUTPUT_NUM_SAMPLES_WRITTEN = Value('i', 0)

        # The total number of samples written to the sound card
        self.SOUND_OUTPUT_NUM_SAMPLES_WRITTEN = Value('i', 0)

        # A value to indicate a runtime error occurred and the program should close. This allows sub-processes to signal
        # to everyone that they have reached an unrepairable state and things need to shutdown.
        self.RUNTIME_ERROR = Value('i', 0)

        # A DatasetLogger object which provides and interface for sending logging messages to the logging process.
        self.logger = logger

    def is_running_well(self):
        return self.RUNTIME_ERROR.value == 0 and self.RUN.value != 0

    def runtime_error(self, excep, error_code):
        sys.stderr.write("RUNTIME ERROR - Unhandled Exception: \n" + str(excep) + "\n")
        traceback.print_exc()
        self.RUN.value = 0
        self.RUNTIME_ERROR.value = -1