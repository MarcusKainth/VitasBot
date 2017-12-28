import inspect

def __func__():
    # emulate __func__ from C++
    return inspect.currentframe().f_back.f_code.co_name