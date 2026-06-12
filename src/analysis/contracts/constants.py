# Centralized metadata contract constants for V1-PFC Predictive Routing (Phase 2C)

TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"

# ============================================================================
# Event Code Constants (MonkeyLogic Behavioral Codes)
# ============================================================================

# Event codes for trial timing and stimulus presentation
EVENT_CODE_FIXATION_CUE = 100  # "fix cue appearance" - NOT p1 stimulus
EVENT_CODE_P1_STIMULUS = 101   # "task_event_2" - p1 stimulus onset (CORRECT ANCHOR)
EVENT_CODE_P2_STIMULUS = 102  # "task_event_3" - p2 stimulus
EVENT_CODE_P3_STIMULUS = 103   # "task_event_4" - p3/omission stimulus position
EVENT_CODE_P4_STIMULUS = 104   # "task_event_5" - p4 stimulus
EVENT_CODE_TRIAL_START = 9      # Trial start
EVENT_CODE_TRIAL_END = 50       # Trial end
EVENT_CODE_REWARD = 96          # Reward delivery
EVENT_CODE_END_CODE = 50        # End code

# Event code to stimulus position mapping
EVENT_CODE_TO_STIMULUS_POS = {
    EVENT_CODE_FIXATION_CUE: "fixation",
    EVENT_CODE_P1_STIMULUS: "p1",
    EVENT_CODE_P2_STIMULUS: "p2", 
    EVENT_CODE_P3_STIMULUS: "p3",
    EVENT_CODE_P4_STIMULUS: "p4",
}

# ============================================================================
# Condition Constants
# ============================================================================

AAXB_CONDITION_NUMBER = 4  # Condition number for AAXB in task_condition_number column

# AAXB omission timing (ms from p1 onset)
# p1 (0ms) -> d1 (531ms) -> p2 (1031ms) -> d2 (1562ms) -> p3/omission (2062ms)
AAXB_OMISSION_OFFSET_MS = 2062
AAXB_OMISSION_SLOT = "p3"  # Omission occurs at presentation 3 in AAXB

# Condition number to label mapping (canonical)
CONDITION_NUMBER_MAP = {
    1: "AAAB",
    2: "AAAB",  # Both 1 and 2 are AAAB (frequent)
    3: "AXAB",
    4: "AAXB",  # Rare, p3 omission
    5: "AAAX",  # Rare, p4 omission
    6: "BBBA",
    7: "BBBA",  # Both 6 and 7 are BBBA (frequent)
    8: "BXBA",
    9: "BBXA",
    10: "BBBX",
}

# Inverse mapping (label to condition numbers)
CONDITION_LABEL_TO_NUMBERS = {
    "AAAB": [1, 2],
    "AXAB": [3],
    "AAXB": [4],
    "AAAX": [5],
    "BBBA": [6, 7],
    "BXBA": [8],
    "BBXA": [9],
    "BBBX": [10],
}

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

