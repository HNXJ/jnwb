# Scientific and Software Contracts v0.9.1

## Scientific Contracts (SC-00X)

These define what must be true about neuroscience. They are non-negotiable.

### SC-001: Raw Data Immutability

**Rule:** Raw recordings and spike times are never modified.

**Rationale:** Silent data mutations are the leading cause of irreproducibility in computational neuroscience.

**Violation:** Any code path that modifies spike times, LFP signals, or epoch timestamps.

**How to satisfy:**
- ✓ `spike_times = dataset.get_spike_times(unit_id)` returns copy
- ✓ `aligned = dataset.with_alignment(...)` returns new Dataset
- ✗ `signal.normalize()` (if mutates signal)
- ✗ `epochs.filter()` (if mutates epochs_df)

**Severity:** CRITICAL

---

### SC-002: Inferential Unit Transparency

**Rule:** Every analysis explicitly declares the unit of inference.

**Rationale:** Silent changes to inference unit (e.g., "I thought I was testing across trials but actually averaged sessions") invalidate statistics.

**Examples:**
- ✓ `Question(inference_unit="unit")`
- ✓ `Question(inference_unit="session")`
- ✗ Averaging across trials without declaring in Question

**Severity:** CRITICAL

---

### SC-003: Alignment as Semantic Labeling

**Rule:** Alignment never modifies timestamps.

**Rationale:** Alignment is where time=0 is; it doesn't change time itself.

**How to satisfy:**
- ✓ `Alignment(name="p1_relative", reference_event="stimulus_onset")`
- ✓ Relabel epoch origins without changing spike times
- ✗ Align by shifting timestamps

**Severity:** MAJOR

---

### SC-004: Signal Class Preservation

**Rule:** SPK, MUAe, and LFP remain conceptually distinct until an explicitly declared integration stage.

**Rationale:** Biological nonsense results if unit and field activity are conflated.

**How to satisfy:**
- ✓ Extract spike_times and lfp separately
- ✓ Combine only in explicitly named "spike_lfp_correlation" analysis
- ✗ Average spikes and LFP together without documentation

**Severity:** MAJOR

---

### SC-005: Trial Identity Preservation

**Rule:** Trial identity is never silently discarded.

**Rationale:** Loss of trial identity loses statistical power and violates assumptions about independence.

**How to satisfy:**
- ✓ `EpochCollection.epochs_df` preserves `trial_num`
- ✓ Averaging must declare level: "across trials", "across units", "across sessions"
- ✗ Aggregating without preserving which trials were included

**Severity:** MAJOR

---

### SC-006: Session Provenance Traceability

**Rule:** Every Dataset, Result, and Figure knows which Session(s) it came from.

**Rationale:** Irreproducibility if you can't trace results back to source NWB files.

**How to satisfy:**
- ✓ `Result.lineage.parents` includes source Sessions
- ✓ `Dataset.metadata['source_sessions']` is always populated
- ✗ Aggregating across sessions without recording which ones

**Severity:** MAJOR

---

## Software Contracts (SW-00X)

These define how the system is built. They can evolve with technology.

### SW-001: Public Objects Immutable

**Rule:** All objects in the public API are immutable (except Figure).

**Rationale:** Immutability enables caching, threading, and reproducibility.

**How to satisfy:**
- ✓ `@dataclass(frozen=True)` for Query, Question, Result, etc.
- ✓ Filtering returns new object: `new_dataset = dataset.where(...)`
- ✗ Mutating methods: `.filter()`, `.normalize()` on frozen objects

**Severity:** MAJOR

---

### SW-002: Backend Independence

**Rule:** Users never see backend details. API is purely in neuroscience language.

**Rationale:** Stable API survives backend changes (NumPy → JAX → Dask).

**How to satisfy:**
- ✓ `result = dataset.answer(question)` (user doesn't choose backend)
- ✗ `result = dataset.answer(question, backend="numpy")`
- ✗ Exposing `numpy`, `scipy.signal`, `matplotlib` in public API

**Severity:** MAJOR

---

### SW-003: No Circular Ownership

**Rule:** If A owns B, B cannot own A.

**Rationale:** Circular dependencies break serialization and create memory leaks.

**How to satisfy:**
- ✓ `Result` owns `Question` (doesn't own `Dataset` which created it)
- ✓ `AlignedDataset` owns `Dataset` and `Alignment`, not vice versa
- ✗ `Dataset` owns `Result` while `Result` owns `Dataset`

**Severity:** MAJOR

---

### SW-004: Objects Serializable

**Rule:** All public objects can serialize to/from JSON.

**Rationale:** Enables reproducible workflows, publication, caching.

**How to satisfy:**
- ✓ `Question.to_dict()` → JSON
- ✓ `Result.to_dict()` → JSON with full provenance
- ✗ Custom Python objects in metadata that can't be serialized

**Severity:** MAJOR

---

### SW-005: API Backwards Compatibility

**Rule:** Within v0.9.x, public API doesn't break. v1.0 freezes forever.

**Rationale:** External code depends on the public API.

**How to satisfy:**
- ✓ Add new parameters with defaults
- ✓ Add new methods
- ✗ Remove methods
- ✗ Change method signatures
- ✗ Change object field types

**Severity:** MINOR

---

## Contract Violations

### How to Report

Code reviews use this format:
```
Reviewer: This PR violates SC-004.
Result owns spike_times and lfp_data without declaring fusion stage.

Author: Actually, fusion happens in PSTHAnalysis.compute().
Let me update Result.metadata to document this.

Reviewer: Good. SC-004 satisfied.
```

### Resolution

1. **Critical violations**: Block merge. Must fix.
2. **Major violations**: Require team discussion and ADR.
3. **Minor violations**: Note for next sprint.

---

## When Contracts Should Be Revisited

- **SC-001**: Only if raw data modification becomes scientifically justified (unlikely)
- **SC-002**: Only if inferential units become ambiguous (never)
- **SW-001**: Only if immutability prevents essential features (needs strong evidence)
- **SW-004**: Only if serialization becomes unnecessary (unlikely)

All other revisions require v2.0 or later.
