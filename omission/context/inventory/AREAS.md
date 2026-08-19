# Area inventory

Version: 2026-07-28
Status: generated inventory, not hand-edited
Truth status: `truth_safe_verified`; regenerate with `python scripts/build_corpus_inventory.py` after any corpus change.


Ten analysis areas. The V3 subdivisions are pooled to **V3a/d**: where a probe spanned several areas its channel axis was divided into equal contiguous shares, so dorsal and ventral V3 are the upper and lower halves of one shank rather than two independently localised areas.


## 1. Coverage

| area | animals | which | sessions | probes | channels | TFR files | units | layer % |
|---|---|---|---|---|---|---|---|---|
| V1 | 2 | C31o, V198o | 9 | 9 | 554 | 108 | 824 | 24.5 |
| V2 | 2 | C31o, V198o | 6 | 6 | 363 | 72 | 757 | 26.4 |
| V3a/d | 2 | C31o, V198o | 10 | 10 | 939 | 204 | 1110 | 38.2 |
| V4 | 3 | C31o, V182o, V198o | 9 | 9 | 768 | 108 | 822 | 38.2 |
| MT | 2 | C31o, V182o | 14 | 14 | 1280 | 168 | 1338 | 50.2 |
| MST | 2 | C31o, V182o | 6 | 6 | 384 | 72 | 290 | 90.9 |
| TEO | 2 | C31o, V182o | 12 | 12 | 1344 | 144 | 778 | 67.6 |
| FST | 2 | C31o, V182o | 2 | 2 | 128 | 24 | 78 | 50.0 |
| FEF | 2 | C31o, V182o | 12 | 14 | 1792 | 168 | 1124 | 61.9 |
| PFC | 2 | C31o, V182o | 14 | 14 | 1792 | 168 | 2107 | 60.2 |


## 2. Animals per area

Every area was recorded in at least two animals, and V4 in all three. The area-by-animal design graph is therefore connected, and additive area and animal effects are jointly identifiable in one model.


| area10 | C31o | V182o | V198o |
|---|---|---|---|
| V1 | 4 | 0 | 5 |
| V2 | 1 | 0 | 5 |
| V3a/d | 5 | 0 | 5 |
| V4 | 6 | 2 | 1 |
| MT | 8 | 6 | 0 |
| MST | 5 | 1 | 0 |
| TEO | 3 | 9 | 0 |
| FST | 1 | 1 | 0 |
| FEF | 2 | 10 | 0 |
| PFC | 6 | 8 | 0 |


(Cells are sessions contributing that area for that animal.)


## 3. Notes

- `channels` counts entries in the per-channel area vector, which assigns each channel to exactly one area. Area labels are disjoint by construction.
- Segment boundaries are an equal-share assumption, not a measurement. Of 28 multi-area probes, 26 split at channel 64 of 128 and the single three-area probe at 42 and 85. No claim depends on the location of a boundary.
- `layer %` differs by nearly threefold across areas, from about 32% in V1 and V2 to over 90% in MST. Laminar contrasts are therefore reported within area and within animal only.
