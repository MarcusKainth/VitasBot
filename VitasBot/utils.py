import inspect

from discord import opus

OPUS_LIBS = ['libopus-0.x86.dll', 'libopus-0.x64.dll', 'libopus-0.dll', 'libopus.so.0', 'libopus.0.dylib']

def __func__():
    # emulate __func__ from C++
    return inspect.currentframe().f_back.f_code.co_name

def load_opus_lib(opus_libs=OPUS_LIBS):
    if opus.is_loaded():
        return True

    for opus_lib in opus_libs:
        try:
            opus.load_opus(opus_lib)
            return True
        except OSError:
            pass

    raise RuntimeError("Could not load an opus lib. Tried {0}".format(
        ", ".join(opus_libs)
    ))