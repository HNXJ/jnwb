- `jnwb.compute_psd` takes keyword-only `nperseg=`, the Welch segment length, from 2 to the
  length along `axis`; a longer segment raises `ValueError` where SciPy would shorten it without
  saying so. The default stays `min(n_times, int(fs))`, now floored at 2 samples: below 2 Hz it
  was 0 or 1.
