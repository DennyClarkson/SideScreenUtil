from __future__ import annotations

import ctypes
import logging

LOGGER = logging.getLogger(__name__)


def trim_unused_working_set() -> None:
    """Offer currently unused runtime pages back to Windows.

    Qt and NumPy touch many DLL/data pages during startup. EmptyWorkingSet does
    not destroy application state; Windows can page a needed shared page back in.
    Calls are deliberately infrequent to avoid churn during live capture.
    """
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
        psapi.EmptyWorkingSet.restype = ctypes.c_int
        process = kernel32.GetCurrentProcess()
        if not psapi.EmptyWorkingSet(process):
            raise ctypes.WinError(ctypes.get_last_error())
    except (AttributeError, OSError):
        LOGGER.debug("Working-set trim is unavailable", exc_info=True)
