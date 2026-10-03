- `jnwb.directed_network` gives the same Granger results whatever the BLAS thread count and
  `n_jobs`. Its residual sums used a threaded BLAS dot product above about ten thousand samples,
  so results moved by up to 1.8e-9 relative between serial and parallel calls. Against the
  previous serial result the largest change is 1.3e-11 absolute.
