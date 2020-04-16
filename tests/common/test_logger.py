import numpy as np
import h5py
import pytest
import os
import time

from flyvr.common.logger import DatasetLogServer, DatasetLogger
from flyvr.common.concurrent_task import ConcurrentTask

# These are some test dataset we will write to HDF5 to check things
test1_dataset = np.zeros((1600,3))
test1_dataset[:,0] = np.arange(0,1600)
test1_dataset[:,1] = np.arange(0,1600)*2
test1_dataset[:,2] = np.arange(0,1600)*3

# A worker thread main that writes the above dataset to the logger in chunks
def log_event_worker(msg_queue, dataset_name, logger, chunk_size):

    logger.create(dataset_name, shape=[512, 3],
                                maxshape=[None, 3],
                                chunks=(512, 3),
                                dtype=np.float64, scaleoffset=8)

    num_chunks = int(test1_dataset.shape[0] / chunk_size)

    assert(test1_dataset.shape[0] % chunk_size == 0)

    # Write the test data in chunk_size chunks
    for i in range(num_chunks):
        data_chunk = test1_dataset[i*chunk_size:(i*chunk_size+chunk_size), :]
        logger.log(dataset_name, data_chunk)

    logger.log(dataset_name=dataset_name, attribute_name='string_attribute', obj='Hello')
    logger.log(dataset_name=dataset_name, attribute_name='num_attribute', obj=50)
    logger.log(dataset_name=dataset_name, attribute_name='array_attribute', obj=np.array([[1, 2], [3, 4]]))


test2_dataset = {"data1": "This is a test", "data2": np.ones(shape=(3,2))}

def log_event_worker2(msg_queue, dataset_name, logger):
        logger.log(dataset_name, test2_dataset)

def test_logger():
    """
    Test the basics of our logger. Doesn't test the mulit-process "safety" because pytest is dumb and causes problems
    with multi-process tests.

    :return: None
    """

    # If we have a test file already, delete it.
    try:
        os.remove('test.h5')
    except OSError:
        pass

    # Start a HDF5 logging server
    server = DatasetLogServer()
    logger = server.start_logging_server("test.h5")

    # Start two processes that will be send log messages simultaneouslly
    #task1 = ConcurrentTask(task=log_event_worker, taskinitargs=["test1", logger])
    #task2 = ConcurrentTask(task=log_event_worker2, taskinitargs=["/deeper/test2/", logger])
    #task1.start()
    #task2.start()
    log_event_worker(None, "test1", logger, chunk_size=1)
    log_event_worker(None, "test2", logger, chunk_size=8)
    log_event_worker2(None, "/deeper/test2/", logger)

    # Wait until they are done
    #while task1.process.is_alive() and task2.process.is_alive():
    #    pass


    # Stop the logging server
    server.stop_logging_server()

    # Wait till it is done
    server.wait_till_close()

    # Make sure the HDF5 file has been created.
    assert(os.path.isfile('test.h5'))

    # Now lets load the HDF5 file we just wrote and make sure it contains the correct stuff
    f = h5py.File('test.h5', 'r')

    # Check if the first dataset exists and  if it is equal to the dataset we have stored in memory
    assert('test1' in f)
    assert(np.array_equal(f['test1'], test1_dataset))

    # Check if the first dataset exists and  if it is equal to the dataset we have stored in memory. We try writing
    # it a second time with different chunk size.
    assert('test2' in f)
    assert(np.array_equal(f['test2'], test1_dataset))


    # Check if the second dataset exists and is equal
    assert('/deeper/test2/data1' in f)
    assert(f['/deeper/test2/data1'].value == test2_dataset['data1'].encode())
    assert('/deeper/test2/data2' in f and np.array_equal(f['/deeper/test2/data2'], test2_dataset['data2']))

    # Check if we saved attributes correctly
    assert(f["test1"].attrs['string_attribute'] == b"Hello")
    assert (f["test1"].attrs['num_attribute'] == 50)
    assert (np.array_equal(f["test1"].attrs['array_attribute'], np.array([[1, 2], [3, 4]])))

    f.close()

    os.remove('test.h5')