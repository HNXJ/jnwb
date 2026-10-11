# Frozen waveform blocks: disposition (todo 11-41)

Result: no frozen file holds misordered waveform blocks, on provenance; the amplitude rule cannot
decide ownership on these files and is not used as the verdict. One question is open (section 5).
Nothing was repaired, relabelled or written to an NWB. Measured 2026-10-11 at jnwb `ecb0ba5b`.

## 1. Scope and integrity (observed)

The 22 `*.nwb` in `F:/nwb-omission/`, the names of `F:/archive/nwb-omission-repair-20260928/SHA256SUMS`
and of the omission freeze receipt (`E:/omission/artifacts/data/nwb_freeze_receipt.json`, 22 files).

| Files | Check | Result |
|---|---|---|
| 10 V182o | whole-file SHA-256 against `SHA256SUMS` (2026-09-28) | 10 match |
| 7 C31o, 5 V198o | omission's dataset fingerprint (`tools/nwb_patch_series_regions.py` `fingerprint`, same skip set) against `fingerprint_after` of `E:/omission/artifacts/analysis/nwb_series_region_patch_20261006/receipt.json`; each patched `electrodes` region against its `new_rows` | 12 match, 12 match |

The 12 differ from `SHA256SUMS` by the 2026-10-06 metadata patch of their series regions, which
re-verified every other dataset. Current whole-file hashes of all 22 are in
`F:/archive/nwb-omission-repair-20260928/SHA256SUMS.post-patch-20261006`, beside the unchanged
original. All 22 files are read-only (Hamm's ruling of 2026-10-10).

## 2. Provenance of the blocks (observed)

Each file's repair receipt (`F:/archive/nwb-omission-repair-20260928/<session>.repair.json`) has a
`waveforms` section naming `jnwb015_waveform_reextract/<session>`, tool commit `8e49dbc6`, seed 0:
the blocks were re-extracted from raw data per unit, in unit order, by the omission repair writer
(`E:/omission/jnwb_ext/waveforms.py:7`). Every file stores a dense `waveform_mean` of shape
`(units, 82, 17)`: 17 channels centred on the stored peak channel, `unit` attribute `volts`.

## 3. The amplitude rule on these files (observed)

`check_waveform_blocks` (dense layout, `ecb0ba5b`) gives 0 owned, all unowned, 0 unknown in every
file at `rtol` 1e-6, 1e-2 and 0.2: `units/amplitude` carries no unit attribute and is in microvolts,
while the blocks are in volts. The median of stored amplitude over the unit's largest channel
peak-to-peak is 0.988e6 to 1.012e6 in every file.

With the amplitude converted to volts (script outside jnwb, same rule), at `rtol` 0.2 the units
other than hardware-channel-0 units match on some channel in 86% (C31o 230901, 598 of 696) to
100% (V182o 260717, 301 of 301) per file, and on the peak channel itself in 54% (C31o 230901,
378 of 696) to 96% (V182o 260708, 311 of 325). The stored amplitude is the sorter's estimate and
the blocks a re-extracted mean, so agreement within 20% is not expected of every unit; a miss is
not evidence of another unit's block. Per-file counts at `rtol` 0.05 and 0.2: section 6.

## 4. Hardware-channel-0 units (observed; their own class, ruling of 2026-10-10)

Units whose `peak_channel_id` resolves (omission `jnwb_ext/unit_channels.electrode_labels`) to an
electrode with `hw_channel` 0: V182o 7 to 55 per file, as omission's record states. The "any
channel" rule calls most of them owned, and every such match checked is spurious: in V182o 260715
the peak-channel peak-to-peak is 78 to 159 uV against a stored 4.7 to 8.5 uV, and the matches fall
on far channels of the window (rows 10 to 16). Hardware-channel-0 units also exist in C31o (0 to 4
per file) and V198o (0 to 8), where omission's record (`E:/omission/context/state/JNWB_REQUESTS.md:864`)
says there are none; C31o 230816 unit 102 stores 3.85 uV against 86.6 uV on its peak channel.
Reported to the omission project.

## 5. Open

| Question | Owner |
|---|---|
| Should `check_waveform_blocks` read an amplitude in another unit than the blocks (a scale or unit keyword, or a refusal when the medians differ by orders of magnitude)? Today it reports every unit unowned on these files | Hamm (public API) |

## 6. Per-file counts, amplitude in volts

Units other than hardware-channel-0 units: owned / unowned on any channel; peak-channel matches.
hw0: hardware-channel-0 units, owned on any channel / on the peak channel.

| File | Units | rtol 0.05 any | rtol 0.05 peak | rtol 0.2 any | rtol 0.2 peak | hw0 | hw0 0.2 any / peak |
|---|---|---|---|---|---|---|---|
| `sub-C31o_ses-230816_rec.nwb` | 357 | 328 / 26 | 301 | 352 / 2 | 325 | 3 | 3 / 1 |
| `sub-C31o_ses-230818_rec.nwb` | 541 | 457 / 82 | 379 | 521 / 18 | 464 | 2 | 2 / 0 |
| `sub-C31o_ses-230823_rec.nwb` | 368 | 331 / 36 | 284 | 366 / 1 | 328 | 1 | 1 / 1 |
| `sub-C31o_ses-230825_rec.nwb` | 491 | 382 / 109 | 309 | 474 / 17 | 405 | 0 | 0 / 0 |
| `sub-C31o_ses-230830_rec.nwb` | 774 | 500 / 270 | 391 | 739 / 31 | 619 | 4 | 4 / 2 |
| `sub-C31o_ses-230831_rec.nwb` | 584 | 417 / 166 | 334 | 556 / 27 | 439 | 1 | 1 / 0 |
| `sub-C31o_ses-230901_rec.nwb` | 696 | 417 / 279 | 249 | 598 / 98 | 378 | 0 | 0 / 0 |
| `sub-V182o_ses-260629.nwb` | 293 | 257 / 29 | 212 | 274 / 12 | 243 | 7 | 6 / 0 |
| `sub-V182o_ses-260702.nwb` | 409 | 340 / 56 | 284 | 374 / 22 | 336 | 13 | 12 / 0 |
| `sub-V182o_ses-260706.nwb` | 212 | 170 / 21 | 126 | 187 / 4 | 148 | 21 | 19 / 2 |
| `sub-V182o_ses-260708.nwb` | 332 | 309 / 16 | 276 | 324 / 1 | 311 | 7 | 7 / 0 |
| `sub-V182o_ses-260710.nwb` | 239 | 153 / 31 | 99 | 177 / 7 | 142 | 55 | 45 / 1 |
| `sub-V182o_ses-260713.nwb` | 374 | 311 / 16 | 276 | 324 / 3 | 305 | 47 | 31 / 1 |
| `sub-V182o_ses-260715.nwb` | 480 | 448 / 26 | 385 | 473 / 1 | 437 | 6 | 5 / 0 |
| `sub-V182o_ses-260717.nwb` | 313 | 283 / 18 | 261 | 301 / 0 | 279 | 12 | 9 / 0 |
| `sub-V182o_ses-260722.nwb` | 252 | 194 / 47 | 144 | 236 / 5 | 203 | 11 | 11 / 0 |
| `sub-V182o_ses-260724.nwb` | 284 | 244 / 23 | 207 | 261 / 6 | 231 | 17 | 16 / 1 |
| `sub-V198o_ses-230629_rec.nwb` | 464 | 435 / 25 | 386 | 455 / 5 | 412 | 4 | 4 / 3 |
| `sub-V198o_ses-230714_rec.nwb` | 589 | 431 / 150 | 330 | 534 / 47 | 447 | 8 | 5 / 2 |
| `sub-V198o_ses-230719_rec.nwb` | 415 | 306 / 103 | 243 | 379 / 30 | 335 | 6 | 6 / 3 |
| `sub-V198o_ses-230720_rec.nwb` | 317 | 247 / 67 | 190 | 293 / 21 | 250 | 3 | 2 / 2 |
| `sub-V198o_ses-230721_rec.nwb` | 277 | 231 / 46 | 196 | 267 / 10 | 233 | 0 | 0 / 0 |
