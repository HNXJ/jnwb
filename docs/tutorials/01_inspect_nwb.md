# Inspect an NWB

Use `jnwb.inspect` to list acquisitions, electrodes, units, and **all** interval tables
without choosing a default event table.

Event **codes** are opaque labels stored in a named column (usually `codes`). jnwb does not
assign scientific meaning to code values. Onset timestamps are in **seconds**.

Run the executable tutorial:

```bash
python examples/tutorials/01_inspect_nwb.py
```

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/01_inspect_nwb.py"
```
