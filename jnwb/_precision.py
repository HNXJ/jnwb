"""One stated precision policy per function, as data a test can read.

Eight mechanisms decided output precision across 21 modules before this file existed, and
three incompatible behaviours coexisted on identical float32 input: upcast, preserve, and
honour-the-request. This module does not migrate them. Changing what the other modules
return would change numeric results package-wide for float32 input, and no single change
can verify that. What it does is *state* which of five behaviours each function follows,
so the policy is a value a test reads rather than a sentence a docstring asserts.

The policies are exhaustive over the declared high-risk subset:

``PRESERVES_INPUT``
    float32 in, float32 out; anything else out as float64. NumPy's own linalg promotion
    rule. :func:`resolve_working_dtype` implements it, so a function claiming this policy
    and the test checking the claim read one implementation rather than two copies.
``ALWAYS_DOUBLE``
    float64 out whatever went in. The function upcasts, and the registry says so instead of
    leaving each caller to discover it.
``BY_REQUEST``
    the caller names the output dtype in a parameter and the function honours it.
``DOUBLE_ONLY``
    float64 out, and a 32-bit *request* is refused rather than silently upcast. Reserved
    for functions where 32 bits would breach a documented tolerance; see
    :class:`jnwb.tfr_accumulator.TFRAccumulator`, whose 32-bit Welford variance misses its
    own documented ``rtol=1e-8`` by 43x to 33973x depending on the mean-to-standard-deviation
    ratio of the power being accumulated.
``NO_FLOAT_OUTPUT``
    the return carries no floating-point field, so no precision policy applies. Recorded
    rather than omitted: "measured, and there is nothing to state" and "nobody looked" are
    different facts, and only one of them is a pass.

:data:`PRECISION_POLICY` is the stated function of input dtype and request that item 06-55
accepts against. It is data, not prose: ``tests/test_precision_switch.py`` reads it and
holds every entry against the live function.
"""

from __future__ import annotations

import numpy as np

#: float32 in, float32 out; everything else float64.
PRESERVES_INPUT = "preserves_input"
#: float64 out whatever went in.
ALWAYS_DOUBLE = "always_double"
#: the caller names the output dtype and the function honours it.
BY_REQUEST = "by_request"
#: float64 out; a 32-bit request is refused, never silently upcast.
DOUBLE_ONLY = "double_only"
#: the return carries no floating-point field.
NO_FLOAT_OUTPUT = "no_float_output"

#: Every policy a registry entry may name.
PRECISION_POLICIES = (
    PRESERVES_INPUT,
    ALWAYS_DOUBLE,
    BY_REQUEST,
    DOUBLE_ONLY,
    NO_FLOAT_OUTPUT,
)

#: Relative error of a 32-bit Welford variance against its 64-bit reference, as a multiple
#: of the ``rtol=1e-8`` that ``tests/test_tfr_accumulator.py`` holds ``var()`` to. Measured
#: over mean-to-standard-deviation ratios of 1, 10, 100, 1000 and 10000 at 200 and 1000
#: trials: the tolerance is breached in every regime, so the refusal below does not depend
#: on choosing an unfavourable one.
WELFORD_32_BIT_TOLERANCE_BREACH = (43, 33973)


class PrecisionNotSupportedError(ValueError):
    """A precision was requested that the function cannot deliver within its tolerance.

    Raised instead of quietly returning the other precision. Item 06-55's stop clause: a
    function that cannot honour 32 bits is recorded 64-bit only and says so, because a
    silent upcast is the caller asking for one thing and receiving another.
    """


def resolve_working_dtype(dtype) -> np.dtype:
    """The single ``PRESERVES_INPUT`` rule, implemented once.

    float32 stays float32; everything else becomes float64. This is NumPy's own ``linalg``
    promotion rule, and it also makes float16 usable, since ``np.linalg.svd`` rejects it
    outright.

    Args:
        dtype: anything ``np.dtype`` accepts.

    Returns:
        The working dtype to compute and return in.
    """
    single = np.dtype(np.float32)
    return single if np.dtype(dtype) == single else np.dtype(np.float64)


#: Dotted name -> policy, for the declared high-risk subset of
#: ``artifacts/evidence/0.2.6/composition_subset_0.2.6.md`` plus the functions item 06-55 repairs.
#:
#: Every entry was measured rather than assumed. The two entries that look like a
#: contradiction are the point: ``to_db`` and ``aggregate_to_db`` live in one module and are
#: documented as the bare and enforcing forms of a single conversion, and they disagree --
#: float32 through ``to_db`` returns float32, the same array through ``aggregate_to_db``
#: returns float64. Naming both here makes the disagreement checkable rather than something
#: a reader might happen to notice.
PRECISION_POLICY = {
    "jnwb.gpu_pca.gpu_pca": PRESERVES_INPUT,
    "jnwb.spectral.to_db": PRESERVES_INPUT,
    "jnwb.tfr.complex_tfr": BY_REQUEST,
    "jnwb.tfr_accumulator.TFRAccumulator": DOUBLE_ONLY,
    "jnwb.spectral.aggregate_to_db": ALWAYS_DOUBLE,
    "jnwb.laminar.vflip": ALWAYS_DOUBLE,
    "jnwb.statistics.cluster_permutation_test": ALWAYS_DOUBLE,
    "jnwb.connectivity.directed_network": ALWAYS_DOUBLE,
    "jnwb.laminar.label_layers": NO_FLOAT_OUTPUT,
    "jnwb.permutation.build_permutation_plan": NO_FLOAT_OUTPUT,
    "jnwb.addressing.enrich_units_dataframe": NO_FLOAT_OUTPUT,
}
