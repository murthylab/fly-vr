import pytest
import numpy as np

from audio.attenuation import Attenuator

def test_attenuate():

    # Create an attenuator with a set of frequencies and their attenuation factors
    att = Attenuator(attenuation_factors=dict(zip([0,100,150,200,250], [3.9273, 0.0701, 0.1178, 0.1851, 0.2132])))

    # Create some test data
    data = np.linspace(1,10, 10)

    # Attenuate the data
    attenuated_data = att.attenuate(data, 200)

    assert attenuated_data[2] == data[2]*att.attenuation_factors[200]

    # Now, attenuate a frequency who is not in the lookup table
    attenuated_data = att.attenuate(data, 220)

    # I precalculate this example, it should equal exactly. The attenuation factor
    # is 0.19634 for 220 Hz
    assert attenuated_data[2] == data[2]*0.19634

def test_load_from_file():

    # Load the attenuation factors from a file
    att = Attenuator.load_from_file("tests/audio/attenuation.txt")

    # Check if the attenuation factor for 250 Hz is 0.2132. This is
    # what should be in the attenuation.txt file.
    assert att.attenuation_factors[250] == 0.2132