

class FlyVRCallback:
    """
    FlyVRCallback is a base class that derived classes should use to implement control logic for closed loop experiments.
    It provides developers with method entry points for injecting custom logic for processing tracking signals and
    triggering stimuli. This class should never be instantiated directly, it provides only an abstract interface.
    """

    def __init__(self, shared_state):
        """
        :param shared_state:
        """
        self.state = shared_state

    def setup_callback(self):
        """
        This method is called once and only once before any event processing is triggered. Place any one time setup
        functionality within this function.

        :return: None
        """
        pass

    def shutdown_callback(self):
        """
        This method is called once and only once before exiting the programe. Place any one time shutdown
        functionality within this function.

        :return: None
        """
        pass

    def process_callback(self, track_state):
        """
        This method is called each time an update is detected in the online tracking state. Code placed within this
        method should execute as quickly and deterministically as possible.

        :param tracking_update: A ctypes structure of type fictrac.SHMEMFicTracState
        :return: None
        """
        pass

    @property
    def logger(self):
        """
        Get access to the HDF5 logging interface.

        :return: A DatasetLogger object setup for creating and logging\appending to HDF5 datasets.
        :rtype: DatasetLogger
        """
        return self.state.logger

    @property
    def options(self):
        """
        Get the options passed to the FlyVR program via the configuration file.

        :return: Get the program configuration options.
        """
        return self.state.options