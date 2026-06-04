#-----------------------------------------------------------------------------
#   Copyright (c) 2008 by David P. D. Moss. All rights reserved.
#
#   Released under the BSD license. See the LICENSE file for details.
#-----------------------------------------------------------------------------
"""
Compatibility wrappers providing uniform behaviour for Python code required to
run under both Python 2.x and 3.x.

All operations emulate 2.x behaviour where applicable.
"""
import sys as _sys

# Python 3.x specific logic.
_sys_maxint = _sys.maxsize

_int_type = int

_str_type = str

_bytes_type = lambda x: bytes(x, 'UTF-8')

_is_str = lambda x: isinstance(x, (str, type(''.encode())))

_is_int = lambda x: isinstance(x, int)

_callable = lambda x: hasattr(x, '__call__')

_dict_keys = lambda x: list(x.keys())

_dict_items = lambda x: list(x.items())

_iter_dict_keys = lambda x: x.keys()

def _bytes_join(*args):
    return ''.encode().join(*args)

def _zip(*args):
    return list(zip(*args))

def _range(*args, **kwargs):
    return list(range(*args, **kwargs))

_iter_range = range

def _iter_next(x):
    return next(x)


from importlib import resources as _importlib_resources

