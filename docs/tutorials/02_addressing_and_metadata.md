# Addressing and Metadata

Discover event codes, retrieve condition onsets strictly in **seconds**, and inspect
units and electrode geometries.

When multiple interval tables exist, specify `table=` explicitly.

![Ten contacts of a synthetic probe by x and z position, colored by layer, and the onsets of two condition codes in seconds](../assets/figures/fig33_addressing_contacts.png#only-light)
![Ten contacts of a synthetic probe by x and z position, colored by layer, and the onsets of two condition codes in seconds](../assets/figures/fig33_addressing_contacts.dark.png#only-dark)

Synthetic: the synthetic NWB fixture's ten contacts from `jnwb.electrode_inventory`, and the two codes of its task table from `jnwb.event_onsets`, which alternate every 0.5 s.

Run the executable tutorial:

```bash
python examples/tutorials/02_addressing_and_metadata.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/02_addressing_and_metadata.py"
```
