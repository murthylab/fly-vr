import PyDAQmx
from PyDAQmx import Task
import numpy as np

value = 1.3

task = Task()
task.CreateAOVoltageChan("/Dev1/ao0","",-10.0,10.0,PyDAQmx.DAQmx_Val_Volts,None)
task.StartTask()
task.WriteAnalogScalarF64(1,10.0,value,None)
task.StopTask()