import os.path

import h5py
import numpy as np
import pandas as pd


STRUCTURE = {
    'fictrac': {'ext': '.h5', 'data': '/fictrac/output', 'sync_info': '', 'base': 'fictrac_frame_num'},
    'daq': {'ext': '.daq.h5', 'data': '/daq/input/samples', 'sync_info': '/daq/input/synchronization_info', 'base': 'daq_input_num_samples_read'},
    'sound': {'ext': '.sound_server.h5',  'data': '', 'sync_info': '/audio/chunk_synchronization_info', 'base': 'sound_output_num_samples_written'},
}


def _get_path(toc, what):
    assert toc.endswith('.toc.yml')
    base = os.path.splitext(os.path.splitext(toc)[0])[0]
    struct = STRUCTURE[what]
    return base + struct['ext']
    


def load_sync_info_fictrac(path):
    with h5py.File(path, mode='r') as f:
        ds = f['/fictrac/output']
        assert ds.attrs['__version'] == 1

        df = pd.DataFrame(ds[:],
                          columns=['frame_cnt',
                                   'del_rot_cam_vec0',
                                   'del_rot_cam_vec1',
                                   'del_rot_cam_vec2',
                                   'del_rot_error',
                                   'del_rot_lab_vec0',
                                   'del_rot_lab_vec1',
                                   'del_rot_lab_vec2',
                                   'abs_ori_cam_vec0',
                                   'abs_ori_cam_vec1',
                                   'abs_ori_cam_vec2',
                                   'abs_ori_lab_vec0',
                                   'abs_ori_lab_vec1',
                                   'abs_ori_lab_vec2',
                                   'posx',
                                   'posy',
                                   'heading',
                                   'direction',
                                   'speed',
                                   'intx',
                                   'inty',
                                   'timestamp',
                                   'seq_num'])


        df['fictrac_frame_num'] = df['frame_cnt'].astype(int)
        df['time_ns'] = (df['timestamp'] * 1e9).astype(int)

        return df.drop_duplicates(subset='time_ns', keep='last'), {'sample_rate': None, 'chunk_size': 1}


def _df_from_h5group(g):
    cols = [g.attrs['column_%d' % i].decode('utf-8') for i in range(len([ci for ci in g.attrs.keys() if ci.startswith('column_')]))]
    return pd.DataFrame(g[:], columns=cols)



def load_sync_info(toc, what):
    path = _get_path(toc, what)

    if what == 'fictrac':
        return load_sync_info_fictrac(path)

    struct = STRUCTURE[what]

    with h5py.File(path, mode='r') as f:
        si = f[struct['sync_info']]

        assert si.attrs['__version'] == 1

        cols = [si.attrs['column_%d' % i].decode('utf-8') for i in range(len([ci for ci in si.attrs.keys() if ci.startswith('column_')]))]

        df = pd.DataFrame(si[:], columns=cols)

        return df, {'sample_rate': si.attrs.get('sample_rate'),
                    'chunk_size': si.attrs.get('sample_buffer_size')}


class _Converter(object):
    def __init__(self, linear_funcs, common_base):
        self._funcs = linear_funcs
        self._common_base = common_base

    def convert_common_base_to_backend(self, val):
        bases = {}
        for what in STRUCTURE:
            try:
                bases[what] = self._funcs[what]['to_base'](val)
            except KeyError:
                continue

        return bases

    def convert_between_backend_timebase(self, from_, to, val, full=False):
        # go from the 'from' backend timebase, to the common timebase, and then to the 'to' backend timebase

        tns = self._funcs[from_]['to_common'](val)
        base = self._funcs[to]['to_base'](tns)

        if full:
            bases = {'tns': tns,
                     STRUCTURE[from_]['base']: val}

            for what in STRUCTURE:
                try:
                    _base = self._funcs[what]['to_base'](tns)
                except KeyError:
                    print("no conversion for", what)
                    continue

                if what == from_:
                    # roundtrip the input
                    bases['%s_ROUNDTRIP' % STRUCTURE[from_]['base']] = _base
                else:
                    bases[what] = _base
                    
            return bases

        return base


# build linear models from each backend's naive timebase back to the common timebase
def build_timebase_converter(toc, common_base='time_ns'):
    assert common_base == 'time_ns'

    linear_funcs = {}

    for what in STRUCTURE:
        df, info = load_sync_info(toc, what)

        if df is None:
            print("no data in", what)
            continue

        df.to_csv('/tmp/%s.csv' % what)

        # some backends, e.g. sound card can have a resolution higer than time_ns
        # so we need to remove duplicate values of time_ns
        #
        # this is a linear model so duplicates are not allowed per axis, but enough
        # observations and this will converge to a good estimate anyway
        if 'time_ns' in df.columns:
            df.drop_duplicates(subset=[common_base], keep='last', inplace=True)

        # to common
        try:
            x = df[common_base]
            assert x.is_unique
        except KeyError:
            print("no", common_base, "in", what)
            continue

        y = df[STRUCTURE[what]['base']]

        coef = np.polyfit(x,y,1)
        invcoef = np.polyfit(y,x,1)
        poly1d_fn = np.poly1d(coef)

        # todo: r2 https://stackoverflow.com/a/66090745

        linear_funcs[what] = {'to_base': np.poly1d(coef),
                              'to_common': np.poly1d(invcoef)}

    print(linear_funcs)

    return _Converter(linear_funcs,
                      common_base=common_base)


def data_to_df(toc, what):
    path = _get_path(toc, what)
    struct = STRUCTURE[what]

    if not struct['data']:
        return None

    with h5py.File(path, mode='r') as f:
        return _df_from_h5group(f[struct['data']])


if __name__ == "__main__":
    import sys
    import yaml
    import matplotlib.pyplot as plt

    toc_path = sys.argv[1]
    converter = build_timebase_converter(toc_path)

    ddf = data_to_df(toc_path, 'daq')
    ddf.to_csv('/tmp/%s.csv' % 'daqdata')

    print(ddf.columns)
    ddf['Copy of Sound card'].plot()

    if 1:
        with open(toc_path, 'r') as f:
            d = yaml.load(f)
        for i in d:
            if i.get('backend') == 'audio':
                print(i)
                print(converter.convert_common_base_to_backend(int(i['time_ns'])))

    plt.show()
