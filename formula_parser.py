"""Compatibility wrapper for the moved formula parser."""

import sys

from stoichio.chemistry import formula_parser as _impl

globals().update(
    {
        name: getattr(_impl, name)
        for name in dir(_impl)
        if not name.startswith("__")
    }
)
sys.modules[__name__] = _impl
