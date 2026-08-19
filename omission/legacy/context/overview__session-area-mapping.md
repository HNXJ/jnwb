---
status: canonical
scope: overview
source_of_truth: true
supersedes: []
last_reviewed: 2026-04-06
---

# Session-Area Mapping

This document details the anatomical mapping of recording probes to brain areas for each session.

## Mapping Logic
1. **Probe Identification**: Channel IDs are sequential (128 per probe).
   - Probe 0: 0-127
   - Probe 1: 128-255
   - Probe 2: 256-383
2. **Area Division**: Labels like `V1, V2` imply a 50/50 split of the 128 channels (0-63 for V1, 64-127 for V2).
3. **Source Metadata**: Area assignments are derived from the NWB `electrodes` table `location` column; laminar positions are derived from the `depth` column.
4. **Aliases**: `DP` is mapped to **V4**.

## Metadata Source Rules
Area assignments are derived deterministically from the NWB `electrodes` table `location` column. Laminar positions are mapped using the `depth` column. If `depth` is missing, it is estimated from the channel index and canonical spacing.

## Master Mapping Table
| Session | Probe | Areas | Channels |
|:---:|:---:|:---|:---:|
| 230629 | 0 | V1, V2 | 128 |
| 230629 | 1 | V3d, V3a | 128 |
| 230630 | 0 | PFC | 128 |
| 230630 | 1 | V4, MT | 128 |
| 230630 | 2 | V3, V1 | 128 |
| 230714 | 0 | V1, V2 | 128 |
| 230714 | 1 | V3d, V3a | 128 |
| 230719 | 0 | V1, V2 | 128 |
| 230719 | 1 | DP (V4) | 128 |
| 230719 | 2 | V3d, V3a | 128 |
| 230720 | 0 | V1, V2 | 128 |
| 230720 | 1 | V3d, V3a | 128 |
| 230721 | 0 | V1, V2 | 128 |
| 230721 | 1 | V3d, V3a | 128 |
| 230816 | 0 | PFC | 128 |
| 230816 | 1 | V4, MT | 128 |
| 230816 | 2 | V3, V1 | 128 |
| 230818 | 0 | PFC | 128 |
| 230818 | 1 | TEO, FST | 128 |
| 230818 | 2 | MT, MST | 128 |
| 230823 | 0 | FEF | 128 |
| 230823 | 1 | MT, MST | 128 |
| 230823 | 2 | V1, V2, V3 | 128 |
| 230825 | 0 | PFC | 128 |
| 230825 | 1 | MT, MST | 128 |
| 230825 | 2 | V4, TEO | 128 |
| 230830 | 0 | PFC | 128 |
| 230830 | 1 | V4, MT | 128 |
| 230830 | 2 | V1, V3 | 128 |
| 230831 | 0 | FEF | 128 |
| 230831 | 1 | MT, MST | 128 |
| 230831 | 2 | V4, TEO | 128 |
| 230901 | 0 | PFC | 128 |
| 230901 | 1 | MT, MST | 128 |

## Canonical Accessor Contract
To ensure consistency across LFP, MUAe, and SPK signals, use the following canonical accessor:

```python
from codes.functions.lfp.lfp_pipeline import get_signal_conditional

result = get_signal_conditional(
    signal_type="MUAe",        # "SPK" | "MUAe" | "LFP"
    condition="AAAB",
    area="V1",
    t_pre_ms=1000,
    t_post_ms=4000,
    align_event="p1",          # Canonical anchor
    target_fs=1000,
)
```

## Anatomical Membership Logic
Use `resolve_area_membership(session_id, probe_id)` for deterministic channel-to-area mapping.

**Example**:
For session `230629`, Probe 0 (`V1, V2`):
- `V1`: Channels `0-63`
- `V2`: Channels `64-127`

For a mixed case (e.g., `V1, V2, V3`):
- Channel boundaries are calculated using `np.linspace(0, 128, n_labels + 1)`.
- This ensures deterministic partitioning across all signal types.
