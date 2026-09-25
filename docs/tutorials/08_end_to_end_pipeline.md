# End-to-End Workflow

A complete workflow demonstrating composition from NWB file inspection, event retrieval,
spiking PSTH calculation, continuous LFP epoching, baseline normalization (decibels last),
connectivity estimation (wPLI), and false discovery rate corrected hypothesis testing.

Run the executable tutorial:

```bash
python examples/tutorials/08_end_to_end_pipeline.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/08_end_to_end_pipeline.py"
```
