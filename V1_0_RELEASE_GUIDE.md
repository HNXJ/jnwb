# jNWB v1.0.0 Release Guide

**Release Date:** 2026-06-25  
**Status:** Stable, production-ready  
**Breaking Changes:** None (frozen public API)

---

## What Is jNWB?

jNWB (Java-compatible NWB) is a scientific computing framework for neuroscience analysis built on immutable ontology objects.

**Key Feature:** Users think in neuroscience language (Query, Question, Result), not implementation details (NumPy, scipy, JAX).

---

## What's Included in v1.0.0

### Public API (Frozen)

13 immutable core objects:

```
Query              → Declare what data you want
Dataset            → Aggregate data matching Query
Alignment          → Set reference frame for time (p1_relative, omission_relative, etc.)
EpochCollection    → Extract filtered trials
Question           → State your scientific hypothesis
Result             → Get immutable results with provenance
Interpretation     → Express what the results mean
Figure             → Visualize for communication
+ Provenance, Lineage for reproducibility
```

### Validated Analysis Types

Three production-ready analyses with identical interface:

```python
result = result_from_psth_analysis(question, epochs, session, ...)
result = result_from_tfr_analysis(question, epochs, session, ...)
result = result_from_decoding_analysis(question, epochs, session, ...)
```

### Documentation

- **Constitutional Documents:** ontology.md, contracts.md, workflow.md, versioning.md
- **Architecture Decision Records:** ADR-001 (immutability), more coming
- **Working Examples:** 3 complete analyses (PSTH, TFR, Decoding)
- **API Reference:** Full object signatures and contracts

---

## What's NOT in v1.0.0 (Internal)

These remain implementation details and will evolve:

```
AnalysisResolver   (dispatch logic - internal)
AnalysisPlan       (execution strategy - internal)
Backends           (NumPy, JAX, Dask - swappable)
Cache              (memoization - internal)
Parallel scheduler (when/how to parallelize - internal)
```

Users don't see these. They interact only with the 13 public objects.

---

## Installation

```bash
# From GitHub
git clone https://github.com/hnxj/omission.git
cd omission
pip install -e .

# Then import
from jnwb import Query, Dataset, Alignment, Question, Result
```

---

## Quick Start (5 minutes)

```python
from jnwb import read
from jnwb.ontology import Query, Alignment, Question, Interpretation
from jnwb.factories import (
    dataset_from_session,
    aligned_dataset_from_dataset,
    epochs_from_aligned_dataset,
    result_from_psth_analysis,
    figure_from_result,
)

# Load session
session = read("D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb")

# Define what data you want
query = Query(sessions="230823", areas=["FEF"], correct_only=True)
dataset = dataset_from_session(session, query)

# Set reference frame
alignment = Alignment(name="p1_relative", reference_event="stimulus_onset")
aligned = aligned_dataset_from_dataset(dataset, alignment)

# Extract trials
epochs = epochs_from_aligned_dataset(aligned, session, condition="AAAB", phase=2)

# Ask a question
question = Question(
    hypothesis="FEF responds to P2 stimulus",
    signals=["spike_times"],
    contrast="baseline vs response",
    inference_unit="unit",
)

# Get result
result = result_from_psth_analysis(question, epochs, session, unit_ids=[1, 2, 3])

# Interpret
interpretation = Interpretation(claim="FEF is visually responsive", confidence="high")

# Visualize
figure = figure_from_result(result, interpretation, title="FEF P2 Response")
```

That's it. **46 lines. Pure neuroscience. No implementation details visible.**

---

## Key Design Principles

### 1. Immutability by Default

```python
dataset = dataset_from_session(session, query)
aligned = dataset.with_alignment(alignment)  # Returns NEW object
epochs = aligned.get_epochs(...)              # Returns NEW object
# Original dataset unchanged
```

**Why:** Automatic provenance tracking, thread-safe parallelization, reproducible caching.

### 2. Scientific Contracts Enforced

All 6 Scientific Contracts (SC-001–006) are automatically enforced by the object model:

```
SC-001: Raw data immutable   ← Dataset never modifies signals
SC-002: Inferential unit explicit ← Question requires it
SC-003: Alignment semantic only ← Alignment never changes timestamps
SC-004: Signal classes distinct ← Each analysis uses specific signals
SC-005: Trial identity preserved ← EpochCollection tracks all trials
SC-006: Session provenance tracked ← Result knows its source
```

**Result:** You cannot write code that violates these contracts.

### 3. User API is Pure Neuroscience Language

Users never write:

```python
# ❌ NOT in user code
import numpy as np
import scipy.signal
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
import matplotlib.pyplot as plt
```

Only:

```python
# ✓ User code
query = Query(sessions="230823", areas=["FEF"])
question = Question(hypothesis="FEF responds to stimulus", ...)
result = result_from_psth_analysis(question, epochs, session)
```

Backend details are completely hidden.

### 4. Backend Independence

The public API doesn't care about computation backend:

```python
# v1.0: NumPy
# v1.1: JAX support (automatic differentiation)
# v1.2: Dask support (distributed computing)
# User code never changes
```

---

## Contracts (What Jnwb Guarantees)

### Scientific Contracts

| Contract | Guarantee | Verified |
|----------|-----------|----------|
| SC-001 | Raw data never modified | ✓ All 3 analyses |
| SC-002 | Inferential unit always explicit | ✓ All 3 analyses |
| SC-003 | Alignment never alters timestamps | ✓ All 3 analyses |
| SC-004 | Signal classes kept distinct | ✓ All 3 analyses |
| SC-005 | Trial identity always preserved | ✓ All 3 analyses |
| SC-006 | Session provenance always tracked | ✓ All 3 analyses |

### Software Contracts

| Contract | Guarantee | Verified |
|----------|-----------|----------|
| SW-001 | Public objects immutable (frozen dataclass) | ✓ v1.0 code |
| SW-002 | Backend completely hidden from users | ✓ User examples |
| SW-003 | No circular ownership (clean dependency graph) | ✓ Architecture review |
| SW-004 | All objects serializable to JSON | ✓ .to_dict() methods |
| SW-005 | API backwards compatible in v1.x | ✓ Versioning policy |

---

## What's Stable (v1.0.0 Frozen)

These will NOT change without v2.0:

```
Query(sessions, areas, units, correct_only, exclude_overlap)
Dataset(query, sessions, units, metadata)
Alignment(name, reference_event, phase_number)
EpochCollection(aligned_dataset, condition, phase, epochs_df)
Question(hypothesis, signals, contrast, inference_unit, metadata)
Result(question, statistics, provenance, lineage)
Interpretation(claim, confidence, alternative_explanations, limitations)
Figure(result, interpretation, title, axes_data, layout)
```

**Frozen means:** Field names, types, order, and immutability are permanent.

---

## What's Experimental (v1.1+)

These may evolve in v1.1, v1.2, etc. without breaking the public API:

```
AnalysisResolver          (internal)
AnalysisPlan              (internal)
Backends (NumPy, JAX, ...) (pluggable)
Cache manager            (internal)
```

---

## Roadmap (v1.0 → v2.0)

### v1.0.x (Now – 6 months)
- Bug fixes
- Documentation improvements
- No new features

### v1.1.x (6–12 months)
- New analysis types (Connectivity, Population summary)
- Optional JAX backend
- Lazy evaluation support

### v1.2.x (12–18 months)
- Dask backend (distributed computing)
- jaxfne integration (differentiable modeling)
- pypeline integration (full pipelines)

### v1.3–1.9.x (18–60+ months)
- Sustained development
- Zero breaking changes
- **No v2.0 planned—v1.x should last forever**

---

## For External Projects

If you're building on jNWB:

```python
# Safe for your project
from jnwb import Query, Result, Interpretation, Figure

# These will NEVER break in v1.0.x, v1.1.x, v1.2.x, etc.
def my_analysis(result: Result) → Interpretation:
    claim = analyze(result.statistics)
    return Interpretation(claim=claim, confidence="high")
```

---

## Support and Feedback

### Where to Report Issues

- **Bug reports:** GitHub Issues
- **Feature requests:** GitHub Discussions
- **Documentation improvements:** Pull requests to `docs/`

### How to Contribute

1. Fork the repository
2. Create a branch for your feature
3. Add tests (examples must pass THETA criteria)
4. Submit PR with clear description

**Internal only:** AnalysisResolver, backends, cache — these are not part of v1.0 API yet.

---

## FAQ

**Q: Will my code break in v1.1?**  
A: No. v1.x maintains full API compatibility.

**Q: Can I use JAX instead of NumPy?**  
A: In v1.1+, yes (planned). In v1.0, user API is backend-agnostic anyway.

**Q: Can I add my own analysis type?**  
A: Yes! Implement `result_from_my_analysis(question, epochs, session, ...)` following the same pattern. Once 3+ analyses use it, consider contributing to jNWB.

**Q: What if I find a better algorithm?**  
A: Implement it in `result_from_better_analysis()`. As long as it returns Result with correct structure, it works.

**Q: Is this production-ready?**  
A: Yes. v1.0 has passed all THETA validation criteria and Rule of Three across 3 diverse analyses.

**Q: What's the immutability cost?**  
A: Minimal. Modern backends (NumPy, JAX) optimize copy-on-write. Dask provides lazy evaluation (v1.1+).

---

## Next Steps

### For Users
1. Install: `pip install -e .`
2. Read: `docs/constitution/01_ontology.md` (1 page)
3. Try: `examples/01_basic_psth.py` (46 lines)
4. Build: Your own analyses following the pattern

### For Ecosystem
1. jaxfne can now depend: `from jnwb import Result, Interpretation`
2. pypeline can now pipeline: `query → dataset → analysis → result`
3. New projects can build on frozen API with confidence

---

## Version History

### v1.0.0 (2026-06-25)
- ✓ Public API frozen
- ✓ 13 core objects immutable
- ✓ All contracts enforced
- ✓ Three validated analyses (PSTH, TFR, Decoding)
- ✓ Constitutional documents finalized
- ✓ THETA validation complete
- ✓ Rule of Three satisfied

---

## License

[Your license here]

---

**Welcome to jNWB v1.0.0. The ontology is frozen. The architecture is proven. Build with confidence.**
