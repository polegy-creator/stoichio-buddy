"""Compatibility wrapper for the moved lab manager."""

import sys

from stoichio import lab_manager as _impl

globals().update(
    {
        name: getattr(_impl, name)
        for name in dir(_impl)
        if not name.startswith("__")
    }
)
sys.modules[__name__] = _impl
