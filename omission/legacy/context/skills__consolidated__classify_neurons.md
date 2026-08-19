# Skill: Putative Neuron Classification
**Purpose**: Generate unit waveform metrics and classify neurons into putative E/I types based on waveform duration and half-width.

## Core API
```python
def classify_neurons(nwb_path: Path, channel_map_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Computes waveform metrics for all units in a session.
    
    Args:
        nwb_path: Path to the frozen NWB file.
        channel_map_path: Optional path to hardware-specific channel maps.
    
    Returns:
        DataFrame with unit metadata, waveform metrics, and E/I classification.
    """
    pass
```

## Implementation Rules
1. **Waveform Metrics**: Compute duration and half-width on the unit's peak channel.
2. **Channel Mapping**: Support optional remapping if a channel map is provided (using the standard probe-local index mapping).
3. **Immutability**: Store results as `putative_typing/metrics_{session_id}.csv` to ensure no changes to source NWB.
4. **Consistency**: Use standardized classification thresholds (e.g., 0.4ms duration) as defined in the project baseline.
