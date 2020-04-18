import time

import h5py
import numpy as np

from flyvr.common.concurrent_task import ConcurrentTask, ConcurrentTaskThreaded

"""
    The logger module implements a thread\process safe interface for logging datasets to a storage backend 
    (HDF5 file currently). It implements this via a multi process client server model of multiple producers (log event
    generators) and a single consumer (log event writer). The main class of interest for users is the DatasetLogServer
    class which maintaints the log server and the DatasetLogger class which is a pickable class that can be sent to 
    other processes for sending log events.
"""


class DatasetLogger(object):
    """
    DatasetLogger is basically a proxy class for sending log events to the DatasetLogServer. This logger class should
    only be instantiated by DatasetLogServer and returned from a call to start_logging_server(). It provides an API
    for creating and writing datasets. It can be called from multiple processes and threads in a safe manner.
    """

    def __init__(self, sender_queue, log_filename=None):
        """
        Create the DatasetLogger for a specific message queue..

        :param sender_queue: The queue to send messages on.
        :param log_filename: The path to the underlying h5 file
        """
        self._sender_queue = sender_queue
        self._log_filename = log_filename

    @property
    def log_filename(self):
        return self._log_filename

    def create(self, *args, **kwargs):
        """
        Create an HDF5 dataset for logging. The arguments for this function is identical to h5py create_dataset command.

        :param name: Name of dataset to create. May be an absolute or relative path. Provide None to create an anonymous dataset, to be linked into the file later.
        :param shape: Shape of new dataset (Tuple).
        :param dtype: Data type for new dataset
        :param data: Initialize dataset to this (NumPy array).
        :param chunks: Chunk shape, or True to enable auto-chunking.
        :param maxshape: Dataset will be resizable up to this shape (Tuple). Automatically enables chunking. Use None for the axes you want to be unlimited.
        :param compression: Compression strategy. See Filter pipeline.
        :param compression_opts: Parameters for compression filter.
        :param scaleoffset: See Scale-Offset filter.
        :param shuffle: Enable shuffle filter (T/F). See Shuffle filter.
        :param fletcher32: Enable Fletcher32 checksum (T/F). See Fletcher32 filter.
        :param fillvalue: This value will be used when reading uninitialized parts of the dataset.
        :param track_times: Enable dataset creation timestamps (T/F).

        :return: None
        """
        create_event = DatasetCreateEvent(args=args, kwargs=kwargs)

        try:
            self._sender_queue.put(create_event)
        except FileNotFoundError:
            pass

    def log(self, dataset_name, obj, append=True, attribute_name=None):
        """
        Write data to a dataset. Supports appending data.


        :param dataset_name: The name of the dataset to modify.
        :param obj: An object to write to the dataset. Currently, this should either be a numpy array or a dictionary
        that contains numpy arrays, strings, or lists, for its values.
        :param append: Should this data be appended based on the last write to this dataset. Only valid for numpy arrays.
        :param attribute_name: If not None, store the object in the attribute called attribute_name. append is ignored.
        :return:
        """

        if attribute_name is None:
            log_event = DatasetWriteEvent(dataset_name=dataset_name, obj=obj, append=append)
        else:
            log_event = AttributeWriteEvent(dataset_name=dataset_name, attribute_name=attribute_name, obj=obj)

        try:
            self._sender_queue.put(log_event)
        except FileNotFoundError:
            pass


class DatasetLogServer(object):
    """
    The DatasetLogServer implements the backend of a thread\process safe interface for logging datasets to a storage
    backend (HDF5 file currently). It implements this via running a separate logging process with a message queue that
    receives logging events from other processes.
    """

    task_cls = ConcurrentTask
    logger_cls = DatasetLogger

    def __init__(self):
        """
        Create the logging server. Does not start the logging process.
        """
        self.log_file_name = None

        self._log_task = self.task_cls(task=self._log_main, comms="queue", taskinitargs=[])

        # For each dataset, we will keep track of the current write position. This will allow us to append to it if
        # nescessary. We will store the write positions as integers in a dictionary of dataset_names
        self.dataset_write_pos = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_logging_server()
        self.wait_till_close()

    @property
    def log_filename(self):
        return self.log_filename

    def start_logging_server(self, filename):
        """
        Start the logging server process. After this method is called log messages (datasets) can be sent to the
        logging server from other processes via the DatasetLogger object that is returned from this method.

        :param filename: The filename to write logged datasets to.
        :return: A DatasetLogger object that provides methods for sending log messages to the server for processing.
        """
        self.log_file_name = filename
        self._log_task.start()

        return self.logger_cls(self._log_task.sender, log_filename=filename)

    def stop_logging_server(self):
        """
        Stop the logging server gracefully. Flush and close the files and make sure all events have been processed.
        :return:
        """
        self._log_task.finish()
        self._log_task.close()
        self.log_file_name = None

    def _log_main(self, frame_queue):
        """
        The main of the logging process.

        :param frame_queue: The message queue from which we will receive log messages.
        :return: None
        """

        # Setup the storage backend
        self._initialize_storage()

        # Run a message processing loop
        run = True
        while run:

            # Get the message
            msg = frame_queue.get()

            # If we get a None msg, its a shutdown signal
            if msg is None:
                run = False
            elif isinstance(msg, DatasetLogEvent):
                msg.process(self)
            else:
                raise ValueError("Bad message sent to logging thread.")

        # Close out the storage
        self._finalize_storage()

    def _initialize_storage(self):
        """
        Setup the storage backend.

        :return:
        """
        self.file = h5py.File(self.log_file_name, "w")

        # Reset all the write positions for any datasets
        self.dataset_write_pos = {}

    def _finalize_storage(self):
        """
        Close out the storage backend.

        :return:
        """

        # Flush and close the log file.
        self.file.flush()
        self.file.close()

    def wait_till_close(self):
        while self._log_task.is_alive():
            time.sleep(0.1)


class DatasetLoggerExplicitFictrac(DatasetLogger):

    pass


class DatasetLogServerThreaded(DatasetLogServer):

    task_cls = ConcurrentTaskThreaded
    logger_cls = DatasetLoggerExplicitFictrac


class DatasetLogEvent:
    """
    DatasetLogEvent is the base class representing dataset logging events. It is not meant to be instatiated
    directly but to serve as a base class for different dataset logging events to inherit from. It provides a common
    interface for the DatasetLogServer to invoke processing.
    """

    def __init__(self, dataset_name):
        """
        Create a dataset log event for a specific dataset

        :param dataset_name: The str name of the dataset for which this event pertains.
        """
        self.dataset_name = dataset_name

    def process(self, server):
        """
        Process this event on the server. This method is not implemented for the base class.

        :param server: The DatasetLogServer object that is receiving this event.
        :return: None
        """
        raise NotImplemented("process is not implemented for base class DatasetLogEvent")


class DatasetCreateEvent(DatasetLogEvent):
    """
    DatasetCreateEvent implements the creation of datasets on the logging servers storage.
    """

    def __init__(self, args, kwargs):
        """
        Create a DatasetCreateEvent with arguments that are passed directly to the storage backed, HDF5 currently.

        :param args: List of arguments to pass to the dataset create command.
        :param kwargs: List of keyword arguments to pass to the dataset create command.
        """

        # We can extract the dataset name from kwargs or args
        try:
            dataset_name = kwargs['name']
        except KeyError:
            dataset_name = args[0]

        # Rather then reimplement all of h5py arguments for dataset create, we just take args and kwargs
        self.args = args
        self.kwargs = kwargs
        super(DatasetCreateEvent, self).__init__(dataset_name)

    def process(self, server):
        """
        Process the event by creating the dataset on the storage backend. args and kwargs are passed directly to the
        create dataset command.

        :param server: The DatasetLogServer to create the dataset on. Should provide an open file to write to.
        :return: None
        """
        server.file.require_dataset(*self.args, **self.kwargs)


class DatasetWriteEvent(DatasetLogEvent):
    """
    The DatasetWriteEvent implements writing to datasets stored on the DatasetLogServer.
    """

    def __init__(self, dataset_name, obj, append=True):
        """
        Create a DatasetWriteEvent that can be sent to the logging server.

        :param dataset_name: The name of the dataset to modify.
        :param obj: An object to write to the dataset. Currently, this should either be a numpy array or a dictionary
        that contains numpy arrays, strings, or lists, for its values.
        :param append: Should this data be appended based on the last write to this dataset. Only valid for numpy arrays.
        """

        if isinstance(obj, np.ndarray):
            self.obj = np.atleast_2d(obj)
        else:
            self.obj = obj

        self.append = append

        super(DatasetWriteEvent, self).__init__(dataset_name)

    def process(self, server):
        """
        Process this event on the logging server.

        :param server: The DataLogServer object that this event was received on. Should have and open file.
        :return: None
        """

        file_handle = server.file

        # Now, if this is a dictionary, we can try to simple write it recusively to this dataset
        if isinstance(self.obj, dict):
            recursively_save_dict_contents_to_group(file_handle, self.dataset_name, self.obj)

        # If we have a numpy array, then we need to write this as a dataset
        elif isinstance(self.obj, np.ndarray):

            # Get a handle to the dataset, we assume it has been created
            dset = file_handle[self.dataset_name]

            # If we are not appending to our dataset, just ovewrite
            if not self.append:

                # Make sure the size of the dataset is identical to the size of the array
                if not np.array_equal(dset.shape, self.obj.shape):
                    raise ValueError("Array cannot be logged to datset name {} because it has incompatible shape!")
                else:
                    dset[:] = self.obj

            else:

                # If we are appending, get the current write position for this dataset. If it doesnt exist, we haven't
                # written yet so lets set it to 0
                try:
                    write_pos = server.dataset_write_pos[self.dataset_name]
                except KeyError:
                    server.dataset_write_pos[self.dataset_name] = 0
                    write_pos = 0

                newsize = write_pos + self.obj.shape[0]

                dset.resize(newsize, axis=0)
                dset[write_pos:, :] = self.obj

                server.dataset_write_pos[self.dataset_name] = dset.shape[0]

        file_handle.flush()


class AttributeWriteEvent(DatasetLogEvent):
    """
    The AttributeWriteEvent implements writing to datasets attributes stored on the DatasetLogServer.
    """

    def __init__(self, dataset_name, attribute_name, obj):
        """
        Create a AttributeWriteEvent that can be sent to the logging server.

        :param dataset_name: The name of the dataset to modify.
        :param attribute_name: The name of the dataset to modify.
        :param obj: An object to write to the dataset attribute.
        """
        self.attribute_name = attribute_name
        self.obj = obj

        super(AttributeWriteEvent, self).__init__(dataset_name)

    def process(self, server):
        """
        Process this event on the logging server.

        :param server: The DataLogServer object that this event was received on. Should have and open file.
        :return: None
        """

        file_handle = server.file

        # Get a handle to the dataset, we assume it has been created
        dset = file_handle[self.dataset_name]

        # Write the attribute
        if isinstance(self.obj, str):
            dset.attrs[self.attribute_name] = np.string_(self.obj)
        else:
            dset.attrs[self.attribute_name] = self.obj

        file_handle.flush()


def test_worker(msg_queue):
    while True:
        print("Test\n")


def recursively_save_dict_contents_to_group(h5file, path, dic):
    """
    Saves dictionary to an HDF5 files, calls itself recursively if items in
    dictionary are not np.ndarray, np.int64, np.float64, str, bytes. Objects
    must be iterable.
    """
    for key, item in list(dic.items()):
        if item is None:
            h5file[path + key] = ""
        elif isinstance(item, bool):
            h5file[path + key] = int(item)
        elif isinstance(item, list):
            items_encoded = []
            for it in item:
                if isinstance(it, str):
                    items_encoded.append(it.encode('utf8'))
                else:
                    items_encoded.append(it)

            h5file[path + key] = np.asarray(items_encoded)
        elif isinstance(item, (str)):
            h5file[path + key] = item.encode('utf8')
        elif isinstance(item, (np.ndarray, np.int64, np.float64, str, bytes, float)):
            h5file[path + key] = item
        elif isinstance(item, dict):
            recursively_save_dict_contents_to_group(h5file, path + key + '/', item)
        else:
            raise ValueError('Cannot save %s type' % type(item))


def make_event_metadata_dtype(metadata):
    type_desc = []
    for field_name in metadata:
        value = metadata[field_name]
        type_desc.append((field_name, type(value)))
