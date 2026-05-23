"""Compatibility wrapper for the moved stoichiometry engine."""

import sys

from stoichio.chemistry import stoich_engine as _impl

globals().update(
    {
        name: getattr(_impl, name)
        for name in dir(_impl)
        if not name.startswith("__")
    }
)
sys.modules[__name__] = _impl
