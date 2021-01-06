import os.path as op
from setuptools import setup, find_packages

this_directory = op.abspath(op.dirname(__file__))
with open(op.join(this_directory, 'README.md'), 'rb') as f:
    long_description = f.read().decode('UTF-8')

setup(
    name='flyvr',
    description='experimental virtual reality setup for flies',
    long_description=long_description,
    long_description_content_type='text/markdown',
    # to distribute package data, add them to MANIFEST.in
    include_package_data=True,
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'PsychoPy==2020.1.2',
        'PyDAQmx==1.4.3',
        'ConfigArgParse',
        'h5py',
    ],
    tests_require=[
        'pytest==5.4.1',
        'pytest-cov==2.8.1',
    ],
    entry_points={
        'console_scripts': [
            'flyvr = flyvr.main:main_launcher',
            'flyvr-fictrac-replay = flyvr.fictrac.replay:main_replay',
            'flyvr-fictrac-plot = flyvr.fictrac.plot_task:main_plot_fictrac',
            'flyvr-fictrac = flyvr.main:main_fictrac',
            'flyvr-daq = flyvr.audio.io_task:main_io',
            'flyvr-print-state = flyvr.common:main_print_state',
            'flyvr-audio = flyvr.audio.sound_server:main_sound_server',
            'flyvr-video = flyvr.video.video_server:main_video_server',
            'flyvr-experiment = flyvr.control.experiment:main_experiment',
            'flyvr-ipc-send = flyvr.common.ipc:main_ipc_send',
            'flyvr-ipc-relay = flyvr.common.ipc:main_relay',
            'flyvr-hwio = flyvr.hwio.phidget:main_phidget',
            'flyvr-gui = flyvr.gui:main_phidget'
        ]
    },
)