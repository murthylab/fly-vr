from flyvr.fictrac.fictrac_driver import FicTracDriver
from flyvr.common.build_arg_parser import parse_arguments

import pytest
import os
import shutil

from distutils.dir_util import copy_tree


@pytest.fixture(autouse=True)
def chdir_back_to_root():
    """
    This fixture makes sure we restore the current working directory after the test.
    """

    # Get the current directory before running the test
    cwd = os.getcwd()

    yield

    # We need chdir back to root of the repo
    os.chdir(cwd)


def test_driver(tmpdir):

    # Copy the stuff we need for fictrac to a temp directory since FicTrac v2 generates a bunch of files
    copy_tree('tests/test_data/fictrac_v2/', tmpdir.strpath)

    shutil.copy('demo_experiment_and_playlist.yml', tmpdir)

    os.chdir(tmpdir)

    driver = FicTracDriver('config.txt', 'output.txt', pgr_enable=False)

    # Get some options so we can pass them to the driver
    opts, parser = parse_arguments("--config demo_experiment_and_playlist.yml", return_parser=True)

    # Normally we would spawn in a separate process but run should terminate because we are working off a video file
    driver.run(options=opts)

    assert False
