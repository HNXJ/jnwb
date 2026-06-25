# Semantic Versioning Policy v1.0

**Status:** Frozen for v1.0+

---

## Overview

jNWB follows Semantic Versioning (semver) with a clear definition of what constitutes breaking changes within the public API.

---

## Public API (Immutable in v1.x)

The following objects and their signatures are frozen until v2.0:

### Core Objects

```python
Query(sessions, areas, units, correct_only, exclude_overlap)
Dataset(query, sessions, units, metadata)
Alignment(name, reference_event, phase_number)
EpochCollection(aligned_dataset, condition, phase, epochs_df)
Question(hypothesis, signals, contrast, inference_unit, metadata)
Result(question, statistics, provenance, lineage)
Interpretation(claim, confidence, alternative_explanations, limitations)
Figure(result, interpretation, title, axes_data, layout)
Provenance(software_version, backend, timestamp, random_seed, parameters, environment)
Lineage(source_type, source_id, parents, operation)
```

### Factory Functions (Public Interface)

```python
dataset_from_session(session, query) → Dataset
aligned_dataset_from_dataset(dataset, alignment) → AlignedDataset
epochs_from_aligned_dataset(aligned_dataset, session, condition, phase, correct_only) → EpochCollection
result_from_psth_analysis(question, epochs, session, unit_ids, baseline_window, response_window) → Result
result_from_tfr_analysis(question, epochs, session, fmin, fmax, n_cycles) → Result
result_from_decoding_analysis(question, epochs, session, classifier_type) → Result
figure_from_result(result, interpretation, title) → Figure
```

### Methods on Public Objects

```
Query.to_dict() → Dict
Dataset.get_spike_times(unit_id) → Optional[np.ndarray]
Result.to_dict() → Dict
Interpretation.to_dict() → Dict
Figure.save(path, format) → None
```

---

## Breaking Changes (Require v2.0)

Any of the following require a major version bump:

### Object Signature Changes

```python
# NOT allowed in v1.x
class Query:
    def __init__(self, sessions, areas, units, correct_only, exclude_overlap, new_param):
        # ^ Adding required parameter breaks existing code
```

### Field Type Changes

```python
# NOT allowed in v1.x
@dataclass(frozen=True)
class Question:
    inference_unit: int  # Was str, now int - breaks existing code
```

### Removing Public Methods

```python
# NOT allowed in v1.x
class Result:
    # Removed: def to_dict(self) - breaks existing code that calls it
```

### Changing Return Types

```python
# NOT allowed in v1.x
def dataset_from_session(...) -> AlignedDataset:  # Was Dataset - breaks callers
    ...
```

### Changing Object Immutability

```python
# NOT allowed in v1.x
@dataclass(frozen=False)  # Was frozen=True - breaks immutability contract
class Query:
    ...
```

---

## Non-Breaking Changes (Allowed in v1.x)

### Adding New Parameters (with defaults)

```python
# ALLOWED in v1.x
def result_from_psth_analysis(
    question, epochs, session, unit_ids,
    baseline_window=(-0.5, 0.0),
    response_window=(0.0, 0.5),
    new_param="default"  # New optional parameter
) → Result:
```

### Adding New Methods

```python
# ALLOWED in v1.x
class Result:
    def to_dict(self) → Dict: ...  # Existing
    def to_json(self) → str: ...    # New method
```

### Adding New Optional Fields to Metadata

```python
# ALLOWED in v1.x
Result.statistics now includes 'new_field': value
```

### Improving Implementations

```python
# ALLOWED in v1.x
- Faster computation
- Better error messages
- More accurate results (bug fixes)
- Backend optimizations
```

### Adding New Analysis Types

```python
# ALLOWED in v1.x
result_from_connectivity_analysis(question, epochs, session) → Result
result_from_population_analysis(question, epochs, session) → Result
```

---

## Version Numbering Scheme

### v1.0.0 (Current Release)

- Public API frozen
- 13 core objects immutable
- All contracts enforced
- Three validated analysis types (PSTH, TFR, Decoding)

### v1.0.x (Patch releases)

- Bug fixes only
- No API changes
- No new features
- Example: v1.0.1 (fix memory leak), v1.0.2 (improve docs)

### v1.1.x (Minor releases)

- New optional parameters
- New methods on existing objects
- New analysis types
- Example: v1.1.0 (add Connectivity analysis), v1.1.1 (add backend='jax' support)

### v1.x.x (Major v1 series)

- Multiple minor releases before v2.0
- v1.5.0 could have 100+ new analyses
- v1.9.9 could have full JAX integration
- **No breaking changes to v1.0.0 API**

### v2.0.0 (Future release)

- Breaking changes allowed
- Redesigns allowed
- Only required if fundamental rethinking needed
- **Not planned. v1.x should sustain 5+ years of development.**

---

## Contract Enforcement

### At Release Time (v1.0.0)

- All 6 Scientific Contracts (SC-001–006) validated
- All 5 Software Contracts (SW-001–005) validated
- API frozen in code and documentation
- Cannot change without v2.0

### During Development (v1.1.x, v1.2.x, etc.)

- Any change violating SC-00X or SW-00X requires major version bump
- Code reviews check: "Does this preserve all contracts?"
- If answer is no, reject the PR and propose v2.0 redesign

### External Dependencies

Projects building on jNWB v1.0.0 are guaranteed:

```python
# Will work forever in v1.x
from jnwb.ontology import Query, Result, Question

query = Query(...)
result = result_from_psth_analysis(...)
# These calls will NEVER break in v1.0.x or v1.1.x or v1.9.x
```

---

## Timeline Expectations

| Version | Timeline | Features |
|---------|----------|----------|
| v1.0.x | Now–6 months | Bug fixes, documentation |
| v1.1.x | 6–12 months | New analyses, optional features |
| v1.2.x | 12–18 months | Ecosystem integration (jaxfne, pypeline) |
| v1.3–1.9 | 18–60 months | Sustained development, no breaking changes |
| v2.0.0 | 60+ months (or never) | Only if fundamental rethinking needed |

---

## Why This Matters

### For Users

```python
# You can write code today knowing it will work in v1.0.x forever
import jnwb

query = jnwb.Query(...)
result = jnwb.psth_analysis(...)
```

### For External Projects

```python
# jaxfne can now safely depend on jnwb
from jnwb import Result, Interpretation
def my_model(result: Result) → Interpretation:
    ...
```

### For Developers

```python
# Code reviews have clear rules
# "Does this break SC-002 or SW-001?"
# If yes → requires v2.0
# If no → allowed in v1.x
```

---

## Deprecation Policy (if ever needed)

Should a feature become obsolete in v1.5.0 but need removal in v2.0:

1. **Mark as deprecated** in v1.5.0: `warnings.warn("deprecated in v1.5, will remove in v2.0")`
2. **Support for 2+ releases**: Work in v1.5.0 and v1.6.0
3. **Remove in v2.0**: Only then deleted

This gives users time to migrate.

---

## Questions Answered by This Policy

**Q: Can I add a new optional parameter?**  
A: Yes, if it has a default value.

**Q: Can I change the type of an existing parameter?**  
A: No. Only in v2.0.

**Q: Can I add a new analysis type?**  
A: Yes. Anytime. No versioning impact.

**Q: Can I change how Result is serialized?**  
A: Only if old serializations still deserialize. Otherwise v2.0.

**Q: Can I optimize performance internally?**  
A: Yes. If output is identical.

**Q: Can I add a new constraint that breaks existing code?**  
A: No. Would violate a contract. Requires v2.0.

---

## Bottom Line

**v1.0.0 API is frozen forever (or until v2.0 redesign).**

Everything in ontology.md and the 13 core objects are immutable contracts.

You can build on this knowing it will not break.
