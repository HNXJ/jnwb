# NWB Basics

Use `jnwb.inspect` to list acquisitions, electrodes, units, and **all** interval tables
without choosing a default event table.

Event **codes** are opaque labels stored in a named column (usually `codes`). jnwb does not
assign scientific meaning to code values. Onset timestamps are in **seconds**.

Run the executable tutorial:

```bash
python examples/tutorials/01_nwb_basics.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/01_nwb_basics.py"
```
