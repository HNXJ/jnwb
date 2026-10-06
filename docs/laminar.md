# Laminar Depth

Four operations read cortical depth from the contacts of one linear probe shaft. Each returns
`accepted=False`, and no depth, when the recording does not support its pattern, so read
`accepted` before any number. Probe geometry and the unit-to-layer lookup are on
[Addressing & Metadata](02_paths_addressing_metadata.md), with the identifiability criteria of
a `zflip` delay; the [laminar tutorial](tutorials/06_laminar.md) runs the same calls on a
longer synthetic session.

| Operation | Reads | Returns |
|---|---|---|
| `vflip` | a channels-by-frequency PSD | the crossover contact between superficial gamma and deep alpha-beta power |
| `label_layers` | an accepted `vflip` result and its probe geometry | `"superficial"`, `"input"`, `"deep"` or `"na"` per contact |
| `xflip` | channels-by-time data or a correlation matrix | contiguous blocks of correlated contacts, tested against surrogates |
| `zflip` | channels-by-time LFP in depth order | the phase-delay gradient across contacts, and an apparent velocity |

## One call each

```python
import numpy as np
import pandas as pd

import jnwb
import jnwb.testing

fs = 1000.0
rec = jnwb.testing.synth_laminar_motif(24, 5000, fs, c_crossover=11.5, pitch_um=100.0,
                                       snr=20.0, rng=0)
electrodes = pd.DataFrame({"x": 0.0, "y": 0.0, "z": 100.0 * np.arange(24),
                           "channel_id": [f"ch{k}" for k in range(24)]})
geom = jnwb.probe_geometry(electrodes, units="um")

# The spectrolaminar crossover, with depth measured from the shallow end of z.
freqs, psd = jnwb.compute_psd(rec.lfp, fs, axis=-1)
fit = jnwb.vflip(psd, freqs, probe_geometry=geom, depth_axis="z", shallow_end="min")
layers = jnwb.label_layers(fit, geom, depth_axis="z", shallow_end="min")
assert fit.accepted and layers["ch0"] == "superficial" and layers["ch23"] == "deep"

# Blocks of 8 and 16 correlated contacts.
data, _, _ = jnwb.testing.synth_correlation_blocks((8, 16), n_samples=400, rng=0)
blocks = jnwb.xflip(data, rng=0)
assert blocks.accepted and blocks.boundaries == (8,)

# One broadband wave reaching each deeper contact 5 ms later.
noise = np.random.default_rng(0)
spectrum = np.fft.rfft(noise.normal(size=4000))
f = np.fft.rfftfreq(4000, 1 / fs)
wave = np.array([np.fft.irfft(spectrum * np.exp(-2j * np.pi * f * 0.005 * k), n=4000)
                 for k in range(6)]) + 0.1 * noise.normal(size=(6, 4000))
delay = jnwb.zflip(wave, fs, orientation="superficial_to_deep", pitch_um=100.0, rng=0)
assert delay.accepted and delay.directionality == "superficial_to_deep"
```

## `vflip` is not the published vFLIP

`vflip` tests for the spectrolaminar motif of Mendoza-Halliday et al. (2024) and shares its
name with that paper's FLIP and frequency-variable vFLIP, not their procedure. The paper
divides each frequency by the power of the channel with the highest power, uses 10-19 Hz and
75-150 Hz, and fits linear regressions over the channel range that maximizes a goodness of
fit; vFLIP also searches over band pairs. `vflip` normalizes by the range across contacts,
uses fixed default bands and scores the fit by its support score, so its crossover is not a
FLIP or vFLIP crossover. Compare a `vflip` crossover with one from the paper's procedure only
as two different estimators.

A fit with no support at all scores `-inf`, so no finite `min_support_score` accepts it.

## Declaring the shallow end

Without a declaration, depth runs from the first row of the probe's shaft order, which can be
the deep end. `depth_axis` and `shallow_end` anchor it at the shallow contact, and
`label_layers` must be given the same pair. The declared column must be monotone along the
shaft: on a staggered shaft the lateral column alternates between the two columns of contacts,
and declaring it raises `ValueError`.

## Reproducing a surrogate test

`xflip` and `zflip` record the seed of their surrogates as `surrogate_seed_entropy`; passing
it back as `rng` reproduces the p-values. For a NumPy `Generator` the seed is one child draw
from it, so the caller's stream advances by one draw.
