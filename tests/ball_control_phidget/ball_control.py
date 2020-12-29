import sys
import time
import random

from Phidget22.Phidget import *
from Phidget22.Devices.Stepper import *
from Phidget22.Net import Net

from flyvr.hwio.phidget import DEFAULT_REMOTE

# FOR THIS SCRIPT TO RUN THE PHIDGET NETWORK SERVER
# MUST BE ENABLED IN THE PHIDGET CONTROL PANEL
# https://www.phidgets.com/docs/Phidget_Control_Panel

# this is a simple script which controls the speed of
# a phidget controlled stepper motor attached to port 0
# of a VINT phidget hub. when launched with no arguments
# the script randomly switches between two speeds in both
# directions, or stopped. when run with an argument it sets
# the stepper to that speed only
# e.g.
#  $ python tests/ball_control_phidget/ball_control.py 600


def main(initial_vel, remote_details=None):
    if remote_details:
        host, port = remote_details
        print("NETWORK", remote_details)
        Net.addServer('localhost', host, port, '', 0)

    stepper0 = Stepper()

    stepper0.setHubPort(0)

    stepper0.openWaitForAttachment(5000)
    stepper0.setControlMode(StepperControlMode.CONTROL_MODE_RUN)
    stepper0.setCurrentLimit(0.8)

    print("Attached: ", stepper0.getAttached())

    if initial_vel is not None:
        vels = (initial_vel,)
    else:
        vels = (-460, -230, 0, 230, 460)

    stepper0.setEngaged(True)

    try:
        while True:
            v = random.choice(vels)
            stepper0.setVelocityLimit(v)
            print("==", v)
            time.sleep(5)
    except KeyboardInterrupt:
        pass

    print("==", 0)
    stepper0.setVelocityLimit(0)
    stepper0.close()


if __name__ == '__main__':
    try:
        vel = int(sys.argv[1])
        assert vel < 3000
        assert vel > -3000
    except IndexError:
        vel = None
    main(vel, remote_details=DEFAULT_REMOTE)
