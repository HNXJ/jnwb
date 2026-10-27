### Filtering and referencing
- `jnwb.bandpass_filter(data, fs, low_cut, high_cut)`: Zero-phase Butterworth bandpass.
- `jnwb.notch_filter(data, fs, freq=60.0, q=30.0)`: IIR notch for line noise.
- `jnwb.bipolar_reference(channel_data, channel_order=None)`: Local differential referencing for spatial artifact reduction.
- `jnwb.laplacian_reference(channel_data, channel_order=None)`: 1-D nearest-neighbor Laplacian along the probe's depth order. Pass `channel_order` unless the array is already in depth order, or the reference is spatially meaningless.
