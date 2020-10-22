import sys
import time
import random

from Phidget22.Phidget import *
from Phidget22.Devices.Stepper import *
import time

vel = int(sys.argv[1])
assert vel < 3000
assert vel > -3000
print("===========", vel)

def main():
    stepper0 = Stepper()

    stepper0.setHubPort(0)

    stepper0.openWaitForAttachment(5000)
    stepper0.setControlMode(StepperControlMode.CONTROL_MODE_RUN)
    stepper0.setCurrentLimit(0.8)
    #stepper0.setMaxVelocityLimit(+3000)
    #stepper0.setMinVelocityLimit(-3000)

    stepper0.setVelocityLimit(vel)

    #stepper0.setTargetPosition(10000)
    stepper0.setEngaged(True)

    try:
        while True:
            v = random.choice((-460, -230, 0, 230, 460))
            stepper0.setVelocityLimit(v)
            print("==", v)
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    #try:
    #    input("Press Enter to Stop\n")
    #except (Exception, KeyboardInterrupt):
    #    pass

    stepper0.setVelocityLimit(0)

    stepper0.close()

main()