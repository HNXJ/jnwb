- `xflip` runs on `vflip2`'s frame (`tests/test_xflip_window.py`). `window=`, an accepted `VFlip2Result` or a
  `(proximal, distal)` pair of probe rows, restricts it to those rows; boundaries are reported in probe rows.
  `contact_spacing` (um) adds `boundaries_um`, measured from row 0, and makes `min_block_size` default to the
  layer 4 thickness in contacts, as `vflip2` sizes its windows. `min_block_size` now defaults to None, which is 2
  without `contact_spacing`; calls without the new arguments are unchanged.
