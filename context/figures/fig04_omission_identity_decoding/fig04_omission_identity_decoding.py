#!/usr/bin/env python3
"""Figure 4 entry point.

The figure is intentionally a thin wrapper around ``fig04_safe_renderer``.  It has no
scientific fallback values: missing or incomplete leakage-safe artifacts are errors.
"""
from __future__ import annotations

from fig04_safe_renderer import build_fig04


if __name__ == "__main__":
    build_fig04()
