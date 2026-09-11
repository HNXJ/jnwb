# Align Spikes and LFP to Events

Retrieve onsets with `jnwb.event_onsets`, unit spike times with `jnwb.unit_spike_times`,
and continuous data with `jnwb.acquisition_channel`, then align with `jnwb.raster_psth`
and spectral primitives.

```bash
python examples/tutorials/03_align_spikes_lfp_to_events.py
```

```python
--8<-- "examples/tutorials/03_align_spikes_lfp_to_events.py"
```
