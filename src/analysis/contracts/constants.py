# Centralized metadata contract constants for V1-PFC Predictive Routing (Phase 2C)

TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"

ALLOWED_SIGNAL_CLASSES = ("SPK", "SUA", "MUAe", "LFP", "behavior", "metadata", "model")

ALLOWED_TIME_BASES = ("p1_relative", "omission_relative", "other_declared")

CANONICAL_AREA_ORDER = ("V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC")

AREA_ALIASES = {
    "DP": "V4",
    "DP (V4)": "V4"
}

GENERIC_UNRESOLVED_AREAS = ("V3",)

AREA_RESOLUTION_STATUSES = (
    "metadata_resolved_channel",
    "metadata_resolved_equal_segment",
    "heuristic_equal_segment",
    "unresolved_generic_v3",
    "unmapped_no_metadata",
    "unknown_area",
    "invalid_probe",
    "invalid_channel",
    "fixture_synthetic",
    "real_metadata_derived",
    "validated",
    "provisional",
    "unresolved",
    "blacklisted"
)

# Standard condition suite definitions (OGLO Suite)
CONDITION_FAMILIES = {
    "A": ("AXAB", "AAXB", "AAAX", "AAAB"),
    "B": ("BXBA", "BBXA", "BBBX", "BBBA"),
    "R": ("RXRR", "RRXR", "RRRX", "RRRR")
}

# Standard sampling rates
DEFAULT_SAMPLING_RATES = {
    "LFP": 1000.0,
    "SPK": 30000.0
}

# Signal class to expected dimensions mapping
SIGNAL_CLASS_DIMS = {
    "SPK": ("trial", "unit", "time"),
    "SUA": ("trial", "unit", "time"),
    "MUAe": ("trial", "channel", "time"),
    "LFP": ("trial", "channel", "time")
}

# Required fields for validation convergence
REQUIRED_SESSION_MANIFEST_FIELDS = ("session_id", "subject", "truth_status", "signal_availability")
REQUIRED_SIGNAL_BLOCK_FIELDS = (
    "data",
    "dims",
    "signal_class",
    "session_id",
    "condition",
    "time_base",
    "alignment_event",
    "window_ms",
    "sampling_rate",
    "unit_or_channel_ids",
    "area_labels",
    "truth_status"
)

