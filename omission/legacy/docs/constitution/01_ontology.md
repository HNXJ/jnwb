# jNWB Ontology v0.9.1

## Core Objects (Frozen Public API)

These 13 objects define the scientific data model. Names and ownership are immutable until v1.0.

| Object | Owns | Cannot Own | Mutable | Serializable |
|--------|------|-----------|---------|--------------|
| **Session** | NWB file handle, metadata | Analyses, Results | No | Yes |
| **Query** | Selection criteria | Data, Sessions | No | Yes |
| **Dataset** | Aggregated unit/LFP data | Sessions (it references them) | No | Yes |
| **Alignment** | Reference frame label | Spike times, signals | No | Yes |
| **EpochCollection** | Filtered trial indices, metadata | Sessions, Signals | No | Yes |
| **Question** | Hypothesis, signals, contrast, inference unit | Data | No | Yes |
| **AnalysisPlan** | Execution strategy, parameters | Results | No | Yes |
| **Result** | Statistics, provenance, lineage | Raw data | No | Yes |
| **Interpretation** | Claims, confidence, limitations | Statistics | No | Yes |
| **Figure** | Rendering, layout, styling | Scientific data | **Yes** | Yes |
| **Provenance** | Execution metadata, parameters | Raw data | No | Yes |
| **Lineage** | Artifact dependencies, parent IDs | Sessions | No | Yes |

## Immutability Rules

**Immutable objects:**
- Session (don't modify NWB files)
- Dataset (filtering returns new Dataset)
- Alignment (semantic label only, never changes timestamps)
- EpochCollection (filtering returns new collection)
- Question (hypotheses are immutable statements)
- AnalysisPlan (execution strategy doesn't change mid-run)
- Result (statistics are facts)
- Interpretation (claims don't change after creation)
- Provenance (execution context is immutable)
- Lineage (artifact origin doesn't change)

**Mutable objects:**
- Figure (styling and layout can evolve; data cannot)

## Ownership Principles

1. **No circular ownership**: A owns B, B cannot own A
2. **Clear hierarchy**: Sessions exist independently; Datasets reference Sessions but don't own them
3. **Immutable data flow**: Data flows downward (Session → Dataset → Result) but never backward
4. **Provenance is universal**: Every object below Dataset has provenance and lineage

## Phase-Out Policy

Old API (OmissionSession method-heavy approach):
```python
session.trial_averaged_plot(...)  # Old
```

New API (ontology-first approach):
```python
result = dataset.answer(question)  # New
```

OmissionSession methods remain in v0.9.x for backwards compatibility.
In v1.0, OmissionSession is deprecated in favor of Query → Dataset → Question → Result.

## Versioning

- **v0.9.x**: OmissionSession + new ontology coexist
- **v1.0**: Frozen public API, ontology is the primary interface
- **v2.0+**: Can only change with semantic versioning

Breaking change definition: any change to these 13 objects' signatures or ownership.
