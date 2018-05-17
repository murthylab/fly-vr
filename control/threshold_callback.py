from control.callback import FlyVRCallback

class ThresholdCallback(FlyVRCallback):
    """
    This class implements control logic for triggering an audio stimulus when tracking velocity reaches a certain
    threshold.
    """

    def __init__(self, shared_state):

        # Call the base class constructor
        super(ThresholdCallback, self).__init__(shared_state=shared_state)

    def _setup_callback(self):
        pass

    def _process_callback(self, track_state):
        pass

    def _shutdown_callback(self):
        pass
