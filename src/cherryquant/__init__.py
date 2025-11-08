"""
CherryQuant core package initialization.

This package provides the core modules for the CherryQuant system.
It exposes a minimal, stable surface at import time and avoids heavy imports
to keep initialization lightweight.
"""

from __future__ import annotations

# Package version (prefer installed metadata, fallback to dev version)
try:
    from importlib import metadata as _importlib_metadata  # Python 3.8+
except Exception:  # pragma: no cover
    _importlib_metadata = None  # type: ignore

try:
    __version__ = _importlib_metadata.version("cherryquant") if _importlib_metadata else "0.0.0"
except Exception:
    __version__ = "0.0.0"

# Optional convenience re-exports (kept lightweight and guarded)
# These imports are wrapped in try/except to avoid hard import-time failures
# if dependencies are not yet installed or when running partial setups.
try:  # pragma: no cover
    from .adapters.data_storage.database_manager import (  # type: ignore
        DatabaseConfig,
        DatabaseManager,
        get_database_manager,
    )

    __all__ = [
        "__version__",
        "DatabaseConfig",
        "DatabaseManager",
        "get_database_manager",
    ]
except Exception:  # pragma: no cover
    __all__ = ["__version__"]


def package_info() -> str:
    """Return a short, human-friendly package info string."""
    return f"CherryQuant {__version__}"
