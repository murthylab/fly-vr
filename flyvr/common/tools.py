import ctypes


def systime():
    """
    Query the windows performance counter to get the current time in milliseconds.

    :return: The current time in milliseconds since this thread started.
    """
    "return a timestamp in milliseconds (ms)"
    tics = ctypes.c_int64()
    freq = ctypes.c_int64()

    # get ticks on the internal ~2MHz QPC clock
    ctypes.windll.Kernel32.QueryPerformanceCounter(ctypes.byref(tics))
    # get the actual freq. of the internal ~2MHz QPC clock
    ctypes.windll.Kernel32.QueryPerformanceFrequency(ctypes.byref(freq))

    t_ms = tics.value * 1e3 / freq.value
    return t_ms


def which(program):
    """
    Locate an executable's path that is on the PATH

    :param program: The name of the executable.
    :return: The full path to the executable
    """
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')

            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def get_flyvr_git_hash():
    hash = None
    try:

        # Find the directory location of the script, the actual repo directory is the parent of this directory
        # because we are in common.
        import os
        repo_dir = os.path.dirname(os.path.realpath(__file__))

        import subprocess
        hash = subprocess.check_output(['git', '--git-dir={}\\..\\.git'.format(repo_dir), 'rev-parse', 'HEAD'])

    except:
        print("Warning: Problem getting git hash for current fly-vr repo. Won't log in experiment output.")

    return hash
