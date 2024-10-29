import ctypes
import numpy as np

MAX_SIZE = 1024
DEV_SIZE = 256

dll_location = "C:\\Windows\\System32\\Ni845x.dll"
#ni845x_dll = ctypes.windll.LoadLibrary('Ni845x.dll') # original
ni845x_dll = ctypes.windll.LoadLibrary(dll_location)



class Ni845xError(Exception):
    def __init__(self, status_code):

        message = ctypes.create_string_buffer(MAX_SIZE)
        
        ni845x_dll.ni845xStatusToString(status_code, MAX_SIZE, message)
        
        Exception.__init__(self, message.value)
        
def errChk(err):
    if err:
        raise Ni845xError(err)


class NI845x():
    VOLTS33 = 33
    VOLTS25 = 25
    VOLTS18 = 18
    VOLTS15 = 15
    VOLTS12 = 12
    INPUT,OUTPUT = 0,1
    kNi845xI2cAddress7Bit = 0
    kNi845xI2cAddress10Bit = 1
    def __init__(self):
       
        # Determine available devices
        NextDevice = ctypes.create_string_buffer(DEV_SIZE)
        FindDeviceHandle = ctypes.c_int32()
        NumberFound = ctypes.c_int32()

        ####WG
        #self.dev_handle = ctypes.c_ulonglong()
        #self.i2c_handle = ctypes.c_ulonglong()


        #NextDevice = ctypes.create_string_buffer(DEV_SIZE)
        #FindDeviceHandle = (ctypes.c_ulong * 5)()
        #ctypes.cast(FindDeviceHandle, ctypes.POINTER(ctypes.c_ulong))
        #NumberFound = (ctypes.c_ulong * 5)()
        #ctypes.cast(NumberFound, ctypes.POINTER(ctypes.c_ulong))
        #######

        errChk(ni845x_dll.ni845xFindDevice(ctypes.byref(NextDevice), ctypes.byref(FindDeviceHandle), ctypes.byref(NumberFound)))

        #if NumberFound.value != 1:
            #raise Exception('Only implemented support for exactly 1 USB card. {} found.'.format(NumberFound.value))
        self._name = NextDevice
        print("self._name before:",self._name)
        self._open()
        print('dev handle', self.dev_handle)
        ni845x_dll.ni845xI2cSetPullupEnable(self.dev_handle, True)
        self.config_i2c()
        self.set_io_voltage_level(self.VOLTS33)
        self.set_port_line_direction_map(self.OUTPUT*np.ones(8))
        
    def _open(self):
        #self.dev_handle = ctypes.c_int32() #self.dev_handle = ctypes.c_ulonglong() , self.dev_handle = ctypes.c_int64()
        self.dev_handle = ctypes.c_ulonglong()
        errChk(ni845x_dll.ni845xOpen(ctypes.byref(self._name), ctypes.byref(self.dev_handle)))
    
    def set_port_line_direction_map(self, mapp, port=0):
        # mapp: np array or list with 8 0's or 1's
        # 0 = input, 1 = output
        port = ctypes.c_uint8(port)
        mapp = np.asarray(mapp)
        assert len(mapp)==8
        r = np.arange(7,-1,-1)
        _map = np.sum(2**r * mapp).astype(int)
        bitmap = ctypes.c_uint8(_map)
        errChk(ni845x_dll.ni845xDioSetPortLineDirectionMap(self.dev_handle, port, bitmap))
        
    def set_io_voltage_level(self, lev):
        lev = ctypes.c_uint8(lev)
        errChk(ni845x_dll.ni845xSetIoVoltageLevel(self.dev_handle, lev))
    
    def end(self):
        errChk(ni845x_dll.ni845xClose(self.dev_handle))
        errChk(ni845x_dll.ni845xI2cConfigurationClose(self.i2c_handle))

    def write_dio(self, line, val, port=0):
        line = ctypes.c_uint8(line)
        port = ctypes.c_uint8(port)
        val = ctypes.c_int32(val)
        errChk(ni845x_dll.ni845xDioWriteLine( self.dev_handle, port, line, val ))
        
    def config_i2c(self, size=None, address=0, clock_rate=100, timeout=2000):#2000
        """
        Set the ni845x I2C configuration.
        
        Parameters
        ----------
            size : Configuration address size (default 7Bit).
            address : Configuration address (default 0).
            clock_rate : Configuration clock rate in kilohertz (default 100).

        Returns
        -------
            None
        """
        if size is None:
            size = self.kNi845xI2cAddress7Bit
        size = ctypes.c_int32(size)
        address = ctypes.c_uint16(address)
        clock_rate = ctypes.c_uint16(clock_rate)
        timeout = ctypes.c_uint32(timeout)
        #
        # create configuration reference
        #
        #self.i2c_handle = ctypes.c_int32() # self.i2c_handle = ctypes.c_ulonglong()
        self.i2c_handle = ctypes.c_ulonglong()
        print('self.i2c_handle:',self.i2c_handle)
        
        errChk(ni845x_dll.ni845xI2cConfigurationOpen(ctypes.byref(self.i2c_handle)))
        
        #
        # configure configuration properties
        #
        
        errChk(ni845x_dll.ni845xI2cConfigurationSetAddressSize(self.i2c_handle, size))
        errChk(ni845x_dll.ni845xI2cConfigurationSetAddress(self.i2c_handle, address))
        errChk(ni845x_dll.ni845xI2cConfigurationSetClockRate(self.i2c_handle, clock_rate))
        errChk(ni845x_dll.ni845xSetTimeout(self.dev_handle, timeout))

        print("address:",address)
        print("size:",size)
        
    def write_i2c(self, data):
        """
        Write an array of data to an I2C slave device.

        Parameters
        ----------
            write_data : Array of bytes to be written. Should be convertible to numpy array of
                    type unsigned char.

        Returns
        -------
            None
            
        """
        #print('Before data: ',data)

        #data = ctypes.create_string_buffer(data)
        nbytes = ctypes.c_int32(len(data)*2)
        #print('nbytes:', nbytes)
    
       # nbytes2 = ctypes.c_int32(len(data))
        #print('nbytes (data):', nbytes2)

        #errChk(ni845x_dll.ni845xI2cWrite(self.dev_handle, self.i2c_handle, nbytes, '171'))#ctypes.byref(data)
        errChk(ni845x_dll.ni845xI2cWrite(self.dev_handle, self.i2c_handle, nbytes, data))#ctypes.byref(data)

        
