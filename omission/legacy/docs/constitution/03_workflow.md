# Scientific Reasoning Workflow v0.9.1

## The Pipeline

Every jNWB analysis follows this pattern:

```
Query
  ↓ creates
Dataset
  ↓ combined with
Alignment
  ↓ creates
AlignedDataset
  ↓ filtered by
EpochCollection
  ↓ answered by
Question
  ↓ internal execution
AnalysisPlan → Analysis.compute()
  ↓ produces
Result
  ↓ interpreted as
Interpretation
  ↓ visualized as
Figure
```

## Stage Descriptions

### 1. Query (What data?)

```python
query = Query(
    sessions=["230823", "230830"],
    areas=["FEF", "PFC"],
    units=None,  # all units
    correct_only=True,
)
```

**Purpose:** Declarative specification of data selection.
**Output:** A request (not executed yet).
**Immutable:** Yes.

### 2. Dataset (Load and aggregate)

```python
dataset = Dataset.from_query(query, nwb_dir="D:/analysis/nwb")
```

**Purpose:** Aggregate data across sessions matching Query.
**Output:** Units, spike times, LFP, metadata.
**Contract:** SC-001, SC-005, SC-006 (immutable, trial identity preserved, provenance tracked).
**Immutable:** Yes.

### 3. Alignment (Set reference frame)

```python
alignment = Alignment(
    name="p1_relative",
    reference_event="stimulus_onset",
    phase_number=2,
)
```

**Purpose:** Define semantic meaning of time=0.
**Examples:** "p1_relative", "omission_slot", "reward_aligned", "fixation_aligned"
**Contract:** SC-003 (never modifies timestamps).
**Immutable:** Yes.

### 4. AlignedDataset (Combine)

```python
aligned = dataset.with_alignment(alignment)
```

**Purpose:** Bundle Dataset with Alignment.
**Output:** Ready for epoch extraction.
**Immutable:** Yes.

### 5. EpochCollection (Filter trials)

```python
epochs = aligned.get_epochs(
    condition="AAAB",
    phase=2,
    correct_only=True,
)
```

**Purpose:** Extract specific trials (subset of Dataset).
**Output:** epoch_times, trial_indices, metadata.
**Contract:** SC-002 (inferential unit explicit in Question), SC-005 (trial identity preserved).
**Immutable:** Yes.

### 6. Question (What are we asking?)

```python
question = Question(
    hypothesis="FEF responds strongly to P2 stimulus",
    signals=["spike_times"],
    contrast="baseline (-500–0ms) vs response (0–500ms)",
    inference_unit="unit",
)
```

**Purpose:** State scientific hypothesis.
**Contract:** SC-002 (inferential unit must be explicit).
**Immutable:** Yes, frozen dataclass.
**Note:** Question never executes itself. It's pure data.

### 7. Analysis (Execution - INTERNAL)

**User sees only:** `result = aligned.answer(question)`

**Internally:**
```
Question
  ↓ sent to
AnalysisResolver
  ↓ determines
AnalysisPlan (execution strategy)
  ↓ sent to
Analysis.compute()
  ↓ produces
Result
```

**User does NOT see:** AnalysisResolver, AnalysisPlan, Analysis class.
**Rationale:** Keep public API stable; implementation details evolve.

### 8. Result (Measured evidence)

```python
result = Result(
    question=question,
    statistics={
        'baseline_rate': 5.2,
        'response_rate': 12.8,
        'pvalue': 0.0012,
        'effect_size': 0.85,
    },
    provenance=Provenance(...),  # software version, timestamp, parameters
    lineage=Lineage(...),         # traces back to Session
)
```

**Purpose:** Immutable output of analysis.
**Contract:** SW-001 (immutable), SW-004 (serializable), SC-001 (never modifies raw data).
**Immutable:** Yes.

### 9. Interpretation (Scientific meaning)

```python
interpretation = Interpretation(
    claim="FEF encodes stimulus intensity",
    confidence="high",
    alternative_explanations=[
        "Could reflect attention redirection",
        "Could reflect motor planning",
    ],
    limitations=[
        "Small sample (n=4 animals)",
        "Cross-session averaging may mask heterogeneity",
    ],
)
```

**Purpose:** Separate measured evidence from scientific argument.
**Contract:** No object owns Interpretation; it's independent analysis by researcher.
**Immutable:** Yes.

### 10. Figure (Communication)

```python
figure = Figure.from_result_and_interpretation(result, interpretation)
figure.save("fef_p2_response.png")
```

**Purpose:** Visualize Result with Interpretation context.
**Contract:** SW-004 (serializable to PNG/PDF/SVG).
**Mutable:** YES (styling, layout can change).
**Note:** Figure never owns raw data; it only references Result.

---

## User-Facing Example (40 lines)

```python
from jnwb import read

# 1. Query: what data?
query = Query(sessions="all", areas=["FEF"])

# 2. Load session
session = read("D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb")

# 3. Create dataset from session
dataset = Dataset.from_session(session, query=query)

# 4. Set alignment
alignment = Alignment(name="p1_relative", reference_event="stimulus_onset")
aligned = dataset.with_alignment(alignment)

# 5. Ask question
question = Question(
    hypothesis="FEF responds to P2",
    signals=["spike_times"],
    contrast="baseline vs response",
    inference_unit="unit",
)

# 6. Get result
result = aligned.answer(question)

# 7. Interpret
interpretation = Interpretation(
    claim="Strong visually-responsive population",
    confidence="high",
)

# 8. Visualize
figure = Figure.from_result_and_interpretation(result, interpretation)
figure.save("output.png")
```

**Key observations:**
- No implementation details visible (NumPy, JAX, FFT, Wilcoxon)
- Every step follows the immutable pattern (creates new object, doesn't mutate)
- Lineage is automatic (result traces back to session)
- Contracts are implicitly satisfied (immutability, unit declaration, alignment semantics)

---

## Contrast: Old vs. New API

### Old (OmissionSession method-heavy)

```python
session = oa.read("...")
session.trial_averaged_plot(area='FEF', phase=2, condition='AAAB')
session.raster_suite(unit_id=42)
```

Problems:
- Methods hide execution strategy
- No explicit Question (is this stimulus response or omission response?)
- No explicit Interpretation (what does this figure mean?)
- Hard to swap analyses (method name is tied to implementation)

### New (Ontology-first)

```python
query = Query(sessions="all", areas=["FEF"])
dataset = Dataset.from_query(query)
question = Question(...)
result = dataset.answer(question)
interpretation = Interpretation(...)
figure = Figure.from_result_and_interpretation(result, interpretation)
```

Advantages:
- Explicit Question separates intent from implementation
- Result is immutable evidence; Interpretation is separate argument
- Easy to swap backends or statistics methods (Question unchanged)
- Composition over method explosion (no need for 100 methods on Session)

---

## When to Revise This Workflow

Only if implementation reveals:
1. A stage is impossible to implement cleanly
2. A stage doesn't generalize to ≥3 analyses
3. A stage violates SC-00X or SW-00X contracts

Otherwise: **freeze and validate through implementation**.
