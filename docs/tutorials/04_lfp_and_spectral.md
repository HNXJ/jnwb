# LFP and Spectral Dynamics

Continuous LFP extraction, event alignment and epoching, Welch PSD, Morlet complex TFR,
baseline power normalization (taking the logarithm last), and weighted phase lag index (wPLI).

Run the executable tutorial:

```bash
python examples/tutorials/04_lfp_and_spectral.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/04_lfp_and_spectral.py"
```
