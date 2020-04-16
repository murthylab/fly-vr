import numpy as np
from scipy.interpolate import interp1d

import flyvr.audio.stimuli


class Attenuator(object):
    def __init__(self, attenuation_factors):
        self.frequencies = list(attenuation_factors.keys())
        self.factors = list(attenuation_factors.values())
        self.attenuation_factors = attenuation_factors

    @classmethod
    def load_from_file(cls, filename):
        af = np.loadtxt(filename)

        frequencies = af[:, 0]
        factors = af[:, 1]

        attenuation_factors = dict(list(zip(frequencies, factors)))

        return cls(attenuation_factors)

    def attenuate(self, data, frequency):

        # Frequency determines the attenuation, if it is None, then just pass
        # back the original data unchanged. Some stimulation data does not
        # need attenuation and this handles those cases.
        if frequency is None:
            return data

        # Otherwise, we need attenuate the data based on the frequency and the pre-loaded
        # attenuation factors.
        else:

            # Lookup the attenuation factor, if we find it, scale the data.
            try:
                attenuation_factor = self.attenuation_factors[frequency]
            except:
                # If we don't find it, then we need to linearly interpolate between the
                # values to get the right factor.

                interpolator = interp1d(list(self.attenuation_factors.keys()), list(self.attenuation_factors.values()),
                                        kind='linear')
                attenuation_factor = interpolator(frequency)

        return data * attenuation_factor
