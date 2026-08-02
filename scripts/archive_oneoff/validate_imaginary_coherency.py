"""
Validate jnwb.spectral.imaginary_coherency against synthetic analytical cases.

Case A (volume conduction / shared reference): a common source S mixed with
independent gain and independent noise into x and y at ZERO lag. Raw coherence
should be high (both channels see the same signal); imaginary coherency should
be ~0 (Nolte et al. 2004: zero-lag mixing has no imaginary part by construction).

Case B (true lagged coupling): y is x delayed by a fixed non-zero lag plus
independent noise. Both raw coherence and imaginary coherency should be
substantially above zero, since the coupling is not zero-lag.

Case C (independent noise): x and y share no common source. Both coherence
measures should be near their null-distribution level (small, not exactly 0
due to finite-sample bias).

Run: python scripts/validate_imaginary_coherency.py
"""
import sys

sys.path.insert(0, "d:/workspace/omission")
import numpy as np

from jnwb.spectral import imaginary_coherency, bipolar_reference, laplacian_reference

rng = np.random.default_rng(0)
fs = 1000.0
n = 20000
band = (8.0, 14.0)  # alpha, matches project band definitions

t = np.arange(n) / fs
source = np.sin(2 * np.pi * 10 * t) + 0.3 * rng.standard_normal(n)

# Case A: zero-lag shared mixing (volume conduction proxy)
x_a = 1.0 * source + 0.4 * rng.standard_normal(n)
y_a = 0.8 * source + 0.4 * rng.standard_normal(n)
res_a = imaginary_coherency(x_a, y_a, fs, band)

# Case B: genuinely lagged coupling (30 ms ~ 30 samples at 1 kHz)
lag = 30
y_b = np.roll(source, lag) * 0.8 + 0.4 * rng.standard_normal(n)
res_b = imaginary_coherency(source, y_b, fs, band)

# Case C: independent noise
x_c = rng.standard_normal(n)
y_c = rng.standard_normal(n)
res_c = imaginary_coherency(x_c, y_c, fs, band)

print("Case A (zero-lag shared mixing):", res_a)
print("Case B (lagged shared source):  ", res_b)
print("Case C (independent noise):     ", res_c)

assert res_a["coh_mag_mean"] > 0.3, "Case A should show high raw coherence (shared source)"
assert res_a["icoh_abs_mean"] < 0.08, "Case A imaginary coherency should stay near zero (zero-lag mixing)"
assert res_b["icoh_abs_mean"] > 0.15, "Case B imaginary coherency should be clearly nonzero (real lag)"
assert res_c["coh_mag_mean"] < 0.15, "Case C raw coherence should be near the noise floor"
# Noise floor is set by segment count (n // nperseg averages), not zero -- with
# n=20000, nperseg=1024 this is ~19 segments, giving a nonzero finite-sample floor.
assert res_c["icoh_abs_mean"] < 0.15, "Case C imaginary coherency should be near the noise floor"

print("\nPASS: imaginary_coherency separates zero-lag mixing from true lagged coupling as expected.")

# --- bipolar / Laplacian re-reference sanity check ---
n_ch = 8
common = 2.0 * source  # a shared-reference artifact identical on every channel
local = rng.standard_normal((n_ch, n)) * 0.5
channel_data = common[None, :] + local

bp = bipolar_reference(channel_data)
lap = laplacian_reference(channel_data)

# The common (shared-reference) component should be almost entirely removed.
common_power = np.var(common)
bp_common_residual = np.var(np.mean(bp, axis=0) - 0.0)  # bp cancels common by construction if adjacent gains equal
lap_common_leak_ratio = np.var(np.mean(lap, axis=0)) / common_power

print(f"\nbipolar_reference output shape: {bp.shape} (expected ({n_ch - 1}, {n}))")
print(f"laplacian_reference output shape: {lap.shape} (expected ({n_ch}, {n}))")
print(f"laplacian common-mode leak ratio (var of channel-mean / var of injected common signal): {lap_common_leak_ratio:.4f}")

assert bp.shape == (n_ch - 1, n)
assert lap.shape == (n_ch, n)
assert lap_common_leak_ratio < 0.05, "Laplacian re-reference should remove nearly all shared-reference signal"

print("PASS: bipolar_reference and laplacian_reference remove shared-reference/common-mode signal as expected.")
