- `jnwb.granger` and `jnwb.granger_causality` raise `ImportError` when `statsmodels`, a
  declared dependency, cannot be imported, where their diagnostics read
  `stationarity_not_tested` and the result was returned. The stationarity p-value is still NaN,
  with that warning, when the Dickey-Fuller fit cannot run on the series (`LinAlgError` or
  `ValueError` from the fit); any other error from the fit now propagates instead of reading as
  NaN.
