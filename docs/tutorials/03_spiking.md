# Spiking Dynamics

Extract sorted unit spike times, calculate trial-aligned PSTHs with causal exponential
smoothing, fit onset latencies, and compute baseline vs response modulation metrics.

Run the executable tutorial:

```bash
python examples/tutorials/03_spiking.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/03_spiking.py"
```
