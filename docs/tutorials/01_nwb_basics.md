# NWB Basics

Use `jnwb.inspect` to list acquisitions, electrodes, units, and **all** interval tables
without choosing a default event table.

Event **codes** are opaque labels stored in a named column (usually `codes`). jnwb does not
assign scientific meaning to code values. Onset timestamps are in **seconds**.

![Onsets of each interval table of a synthetic session on a time axis in seconds, and the spacing between onsets in each table](../assets/figures/fig32_interval_tables.png#only-light)
![Onsets of each interval table of a synthetic session on a time axis in seconds, and the spacing between onsets in each table](../assets/figures/fig32_interval_tables.dark.png#only-dark)

Synthetic: the synthetic NWB fixture's interval tables, as `jnwb.inspect` lists them, with onsets from `jnwb.event_onsets`. The detected-change tables hold onsets at 0 to 0.2 s, and the flash table at 20 to 21.8 s.

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
