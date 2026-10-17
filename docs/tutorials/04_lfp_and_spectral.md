# LFP and Spectral Dynamics

Continuous LFP extraction, event alignment and epoching, Welch PSD, Morlet complex TFR,
baseline power normalization (taking the logarithm last), and weighted phase lag index (wPLI).

Run the executable tutorial:

```bash
python examples/tutorials/04_lfp_and_spectral.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## The figure

![Spectrum and wPLI of two synthetic LFP channels sharing a lagged rhythm](../assets/figures/fig28_lfp_spectral_wpli.png#only-light)
![Spectrum and wPLI of two synthetic LFP channels sharing a lagged rhythm](../assets/figures/fig28_lfp_spectral_wpli.dark.png#only-dark)

Synthetic, not the tutorial's fixture: two LFP channels sharing a 20 Hz rhythm with a fixed lag on one channel, plus independent noise. Panel A is the Welch spectrum from `jnwb.compute_psd` with the 15 to 30 Hz band shaded; panel B is the wPLI spectrum of `jnwb.wpli` for the lagged pair against an independent-noise control, with each band mean in the legend.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/04_lfp_and_spectral.py"
```
