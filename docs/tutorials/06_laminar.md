# Laminar Electrophysiology

One-dimensional current source density (CSD), spectrolaminar alignment with vFLIP,
inter-contact phase gradient and traveling wave estimation with zFLIP, and contiguous
correlation blocks with xFLIP, all on synthetic signals.

Run the executable tutorial:

```bash
python examples/tutorials/06_laminar.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## The figure

![Synthetic laminar signals: current source density, vFLIP band profiles, zFLIP wPLI and xFLIP contact correlation](../assets/figures/fig25_laminar_csd_flips.png#only-light)
![Synthetic laminar signals: current source density, vFLIP band profiles, zFLIP wPLI and xFLIP contact correlation](../assets/figures/fig25_laminar_csd_flips.dark.png#only-dark)

Synthetic: the seeded signals the tutorial builds, a shared rhythm with a phase lag per contact and two blocks of correlated contacts. Panel A is the current source density (`jnwb.current_source_density_1d`), normalized to its peak. Panel B is the vFLIP band profiles; the estimator is `jnwb.vflip`, applied to the Welch spectrum by `jnwb.vflip_from_lfp`. For these signals it rejects the crossover, and the legend gives its reason. Panel C is the wPLI between adjacent contacts from zFLIP (`jnwb.zflip`); its legend gives the apparent velocity and the surrogate p. Panel D is the correlation between contacts, with the omnibus p of `jnwb.xflip` in its legend.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/06_laminar.py"
```
