import sys
import traceback

from multiprocessing import Value


# noinspection PyPep8Naming
class SharedState(object):
    """
    A class to represent the shared state between our concurrent tasks. We can add values to this shared state and they
    will be passed as an argument to all tasks. This allows us to communicate with thread safe shared variables.
    """
    def __init__(self, options, logger):

        # Lets store the options passed to the program. This does not need to be stored in a thread
        # safe manner.
        self._options = options
        self._logger = logger

        self._run = Value('i', 1)
        self._runtime_error = Value('i', 0)
        self._daq_ready = Value('i', 0)
        self._start_daq = Value('i', 0)
        self._fictrac_ready = Value('i', 0)
        self._fictrac_frame_num = Value('i', 0)
        self._daq_output_num_samples_written = Value('i', 0)
        self._sound_output_num_samples_written = Value('i', 0)

    @property
    def SOUND_OUTPUT_NUM_SAMPLES_WRITTEN(self):
        """ total number of sound samples written """
        return self._sound_output_num_samples_written.value

    @SOUND_OUTPUT_NUM_SAMPLES_WRITTEN.setter
    def SOUND_OUTPUT_NUM_SAMPLES_WRITTEN(self, v):
        self._sound_output_num_samples_written.value = v

    @property
    def DAQ_OUTPUT_NUM_SAMPLES_WRITTEN(self):
        """ total number of samples written to the DAQ """
        return self._daq_output_num_samples_written.value

    @DAQ_OUTPUT_NUM_SAMPLES_WRITTEN.setter
    def DAQ_OUTPUT_NUM_SAMPLES_WRITTEN(self, v):
        self._daq_output_num_samples_written.value = v

    @property
    def FICTRAC_READY(self):
        """ FicTrac is running an processing frames """
        return self._fictrac_ready.value

    @FICTRAC_READY.setter
    def FICTRAC_READY(self, v):
        self._fictrac_ready.value = v

    @property
    def FICTRAC_FRAME_NUM(self):
        """ FicTrac frame number """
        return self._fictrac_frame_num.value

    @FICTRAC_FRAME_NUM.setter
    def FICTRAC_FRAME_NUM(self, v):
        self._fictrac_frame_num.value = v

    @property
    def START_DAQ(self):
        """ DAQ should start playback and acquisition """
        return self._start_daq.value

    @START_DAQ.setter
    def START_DAQ(self, v):
        self._start_daq.value = v

    @property
    def RUN(self):
        """ the current run state """
        return self._run.value

    @RUN.setter
    def RUN(self, v):
        self._run.value = v

    @property
    def RUNTIME_ERROR(self):
        """  a value to indicate a runtime error occurred and the whole of flyvr program should close """
        return self._runtime_error.value

    @RUNTIME_ERROR.setter
    def RUNTIME_ERROR(self, v):
        self._runtime_error.value = v

    @property
    def DAQ_READY(self):
        """ the daq is aquiring samples """
        return self._daq_ready.value

    @DAQ_READY.setter
    def DAQ_READY(self, v):
        self._daq_ready.value = v

    @property
    def logger(self):
        """ an object which provides and interface for sending logging messages to the logging process """
        return self._logger

    @property
    def options(self):
        """ runtime / command line config options """
        return self._options

    def is_running_well(self):
        return self.RUNTIME_ERROR == 0 and self.RUN != 0

    def runtime_error(self, excep, error_code):
        sys.stderr.write("RUNTIME ERROR - Unhandled Exception: \n" + str(excep) + "\n")
        traceback.print_exc()
        self.RUN = 0
        self.RUNTIME_ERROR = -1