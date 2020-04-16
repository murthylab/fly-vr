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
    extras_require={
        'bloscpack': ['bloscpack']
    },
    entry_points={
        'console_scripts': [
            'flyvr = flyvr.main:main_launcher',
            'imgstore-save = imgstore.apps:main_saver',
            'imgstore-test = imgstore.apps:main_test',
        ]
    },
)