"""Public import target: import jnwb."""

from src.jnwb import *  # noqa: F403
from src.jnwb import __all__ as __all__  # noqa: F401

# Re-export submodules for advanced imports (src.jnwb.errors, etc.)
from src.jnwb import (  # noqa: F401
    artifacts,
    backends,
    epochs,
    errors,
    files,
    qc,
    schema,
    signals,
    task,
)
