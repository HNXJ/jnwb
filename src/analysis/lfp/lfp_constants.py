"""
lfp_constants.py
Shared constants for LFP Omission analysis (V4 Suite).
Combines standardized timing, hierarchical tiers, and project-specific aesthetics.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List, Any

# Canonical LFP sampling rate — propagated to lfp_tfr, lfp_preproc
FS_LFP: float = 1000.0

# Project Aesthetic: Madelane Golden Dark + ordered omission palette
GOLD = "#CFB87C"
BLUE = "#2563EB"
VIOLET = "#8F00FF"
RED = "#DC2626"
GREEN = "#16A34A"
BLACK = "#000000"
PINK = "#FF1493"
BROWN = "#8B4513"
TEAL = "#00FFCC"
ORANGE = "#FF5E00"
RED_BEIGE = "#C9A88A"
GRAY = "#D3D3D3"
WHITE = "#FFFFFF"
SLATE = "#444444"

# Canonical ordered palette for bands, conditions, and series (index 0..12).
# Assign by position; do not invent ad-hoc colors outside this list.
OMISSION_PALETTE_ORDER: List[str] = [
    "GOLD",
    "BLUE",
    "VIOLET",
    "RED",
    "GREEN",
    "BLACK",
    "PINK",
    "BROWN",
    "TEAL",
    "ORANGE",
    "RED_BEIGE",
    "GRAY",
    "WHITE",
]

OMISSION_PALETTE: Dict[str, str] = {
    "GOLD": GOLD,
    "BLUE": BLUE,
    "VIOLET": VIOLET,
    "RED": RED,
    "GREEN": GREEN,
    "BLACK": BLACK,
    "PINK": PINK,
    "BROWN": BROWN,
    "TEAL": TEAL,
    "ORANGE": ORANGE,
    "RED_BEIGE": RED_BEIGE,
    "GRAY": GRAY,
    "WHITE": WHITE,
}


def omission_palette_hex(index: int) -> str:
    """Return palette hex by 0-based index (wraps if index >= len)."""
    name = OMISSION_PALETTE_ORDER[index % len(OMISSION_PALETTE_ORDER)]
    return OMISSION_PALETTE[name]


def colors_for_bands(
    bands: Dict[str, Tuple[int, int]] | None = None,
) -> Dict[str, str]:
    """Map band names to palette colors in canonical band order."""
    if bands is None:
        bands = BANDS
    return {name: omission_palette_hex(i) for i, name in enumerate(bands.keys())}

# --- Area Naming and Hierarchy ---
CANONICAL_AREAS: List[str] = ['V1', 'V2', 'V3d', 'V3a', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']

AREA_ALIAS_MAP: Dict[str, str] = {
    'DP': 'V4',
}

HIERARCHY: Dict[str, List[str]] = {
    "Low": ["V1", "V2"],
    "Mid": ["V3d", "V3a", "V4", "MT", "MST", "TEO", "FST"],
    "High": ["FEF", "PFC"]
}

AREA_TIERS: Dict[str, List[str]] = {k.lower(): v for k, v in HIERARCHY.items()}

# --- Timing Constants (in milliseconds from P1 onset = 0ms) ---


SEQUENCE_TIMING_MS: Dict[str, Dict[str, Any]] = {
    "p1": {"start": 0, "end": 531, "color": GOLD},
    "d1": {"start": 531, "end": 1031, "color": GRAY},
    "p2": {"start": 1031, "end": 1562, "color": VIOLET},
    "d2": {"start": 1562, "end": 2062, "color": GRAY},
    "p3": {"start": 2062, "end": 2593, "color": TEAL},
    "d3": {"start": 2593, "end": 3093, "color": GRAY},
    "p4": {"start": 3093, "end": 3624, "color": ORANGE},
    "d4": {"start": 3624, "end": 4124, "color": GRAY}
}

TIMING_MS: Dict[str, int] = {name: info["start"] for name, info in SEQUENCE_TIMING_MS.items()}
TIMING_MS["fx"] = -500    # fixation window: -500ms to 0ms (baseline)

EVENT_LINES_MS: Dict[str, int] = TIMING_MS.copy()

# Omission timings for analysis windows (ms, from p1 onset = 0ms)
OMISSION_ANALYSIS_WINDOWS_MS: Dict[str, Tuple[int, int]] = {
    'AXAB': (SEQUENCE_TIMING_MS['p2']['start'], SEQUENCE_TIMING_MS['p2']['end']),
    'BXBA': (SEQUENCE_TIMING_MS['p2']['start'], SEQUENCE_TIMING_MS['p2']['end']),
    'RXRR': (SEQUENCE_TIMING_MS['p2']['start'], SEQUENCE_TIMING_MS['p2']['end']),
    'AAXB': (SEQUENCE_TIMING_MS['p3']['start'], SEQUENCE_TIMING_MS['p3']['end']),
    'BBXA': (SEQUENCE_TIMING_MS['p3']['start'], SEQUENCE_TIMING_MS['p3']['end']),
    'RRXR': (SEQUENCE_TIMING_MS['p3']['start'], SEQUENCE_TIMING_MS['p3']['end']),
    'AAAX': (SEQUENCE_TIMING_MS['p4']['start'], SEQUENCE_TIMING_MS['p4']['end']),
    'BBBX': (SEQUENCE_TIMING_MS['p4']['start'], SEQUENCE_TIMING_MS['p4']['end']),
    'RRRX': (SEQUENCE_TIMING_MS['p4']['start'], SEQUENCE_TIMING_MS['p4']['end'])
}

# Patch windows for specific analysis
OMISSION_PATCH_WINDOWS_MS: Dict[str, Tuple[int, int]] = {
    'p2': (SEQUENCE_TIMING_MS['p2']['start'], SEQUENCE_TIMING_MS['p2']['end']),
    'p3': (SEQUENCE_TIMING_MS['p3']['start'], SEQUENCE_TIMING_MS['p3']['end']),
    'p4': (SEQUENCE_TIMING_MS['p4']['start'], SEQUENCE_TIMING_MS['p4']['end'])
}

# --- Other Constants ---

# Standard Frequency Bands
BANDS: Dict[str, Tuple[int, int]] = {
    "Theta": (3, 7),
    "Alpha": (8, 12),
    "l-beta": (14, 20),
    "h-beta": (20, 30),
    "Gamma_L": (32, 80),
    "Gamma_H": (80, 200)
}

# All OGLO conditions
ALL_CONDITIONS: List[str] = [
    "AAAB", "AXAB", "AAXB", "AAAX",
    "BBBA", "BXBA", "BBXA", "BBBX",
    "RRRR", "RXRR", "RRXR", "RRRX",
]

OMISSION_CONDITIONS: List[str] = [c for c in ALL_CONDITIONS if "X" in c]

# Map Labels to task_condition_number as found in NWB intervals
# Mapping derived from actual data audit:
CONDITION_MAP: Dict[str, List[int]] = {
    "RRRR": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26],
    "AXAB": [3],
    "BXBA": [8],
    "RXRR": [27, 28, 29, 30, 31, 32, 33, 34],
    "AAXB": [4],
    "BBXA": [9],
    "RRXR": [35, 37, 39, 41],
    "AAAX": [5],
    "BBBX": [10],
    "RRRX": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
    "AAAB": [1, 2],
    "BBBA": [6, 7]
}
print(f"""[action] CONDITION_MAP updated with observed NWB codes""")

DEFAULT_WF_PARAMS: Dict[str, Any] = {
    "window": "hann",
    "nperseg": 256,
    "noverlap": int(0.98 * 256),
}

@dataclass(frozen=True)
class FigureSpec:
    name: str
    title: str
    output_dir: Path
    conditions: List[str]
    sequence: str
    analysis: str
