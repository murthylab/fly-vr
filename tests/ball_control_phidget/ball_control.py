import sys
import time
import random

from Phidget22.Phidget import *
from Phidget22.Devices.Stepper import *
from Phidget22.Net import Net

from flyvr.hwio.phidget import DEFAULT_REMOTE


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