import pytest

from flyvr.audio.io_task import IOTask, DAQ_NUM_OUTPUT_SAMPLES, DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT
from flyvr.common import SharedState
from flyvr.common.logger import DatasetLogServer
from flyvr.audio.signal_producer import SampleChunk


@pytest.mark.use_daq
def test_io_a_output(tmpdir):
    import time

    import h5py

    with DatasetLogServer() as log_server:

        shared_state = SharedState(None, logger=log_server.start_logging_server(tmpdir.join('test.h5').strpath))

        taskAO = IOTask(cha_name=['ao1'], cha_type="output",
                        num_samples_per_chan=DAQ_NUM_OUTPUT_SAMPLES,
                        num_samples_per_event=DAQ_NUM_OUTPUT_SAMPLES_PER_EVENT,
                        shared_state=shared_state)

        taskAO.StartTask()
        for i in range(10):
            time.sleep(0.1)

        taskAO.StopTask()
        taskAO.stop()
        taskAO.ClearTask()

    with h5py.File(shared_state.logger.log_filename, mode='r') as h5:
        assert h5['daq']['chunk_synchronization_info'].shape[-1] == SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS
