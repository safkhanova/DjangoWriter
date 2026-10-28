"""
emailotp/translation.py — the single seam between this package and whatever
translation backend the host project uses.

The package never imports the project. It asks for a callable with the
signature `(key, default) -> str` via the EMAILOTP_TRANSLATE setting.
"""
from django.utils.functional import lazy
from django.utils.module_loading import import_string

from . import conf

_resolved = None
_MISSING = object()


def _backend():
    """Import the configured callable once and cache it."""
    global _resolved
    if _resolved is None:
        path = conf.TRANSLATE
        _resolved = import_string(path) if path else _MISSING
    return None if _resolved is _MISSING else _resolved


def tr(key, default=''):
    """Look up `key`, falling back to `default`. Never raises."""
    backend = _backend()
    if backend is None:
        return default or key
    try:
        return backend(key, default)
    except Exception:
        return default or key


# For form labels, which are built before a request exists.
tr_lazy = lazy(tr, str)
