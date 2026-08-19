# ADR-001: Immutable Datasets

**Status:** DECIDED (v0.9.1)

## Decision

Datasets are immutable. Filtering operations (`.where()`, `.select()`, `.with_alignment()`) return new Dataset instances rather than mutating in place.

## Rationale

1. **Automatic lineage tracking**: Every transform creates a new object, so you can trace backwards to the source. This is implemented transparently; users don't need to manually manage provenance.

2. **Thread-safe parallelization**: Immutable objects can be safely passed to multiple threads without locks or race conditions.

3. **Caching**: Hash-based caching becomes straightforward when objects are immutable and therefore never change identity.

4. **Reproducibility**: An immutable Dataset with provenance is a complete record of where the data came from and what selections were applied.

5. **Compatibility with xarray/pandas patterns**: Both use immutable-by-pattern (`.where()` returns new object) and the API is familiar to scientific Python users.

## Alternatives Considered

### 1. Mutable Datasets with `.filter()` Methods

```python
dataset.filter(areas=["FEF"])  # Mutates in place
```

**Rejected because:**
- Breaks lineage tracking (original dataset is lost)
- Requires defensive copying everywhere
- Confusing semantics (is the object before or after filtering?)

### 2. Copy-on-Write Semantics

```python
filtered = dataset.filter(...)  # Copies only if needed
```

**Rejected because:**
- Unpredictable performance (sometimes fast, sometimes slow)
- Users must understand when copies happen
- Harder to implement correctly

### 3. Explicit Snapshot Management

```python
snapshot = dataset.snapshot()  # Manual provenance tracking
filtered = snapshot.filter(...)
```

**Rejected because:**
- Verbose API
- Users responsible for provenance (easy to forget)
- Doesn't scale with many filtering operations

## Consequences

### Positive
- Automatic lineage and provenance tracking
- Thread-safe for parallelization
- Cache-friendly
- Clear semantics (filtering always creates new object)
- Familiar to xarray/pandas users

### Negative
- More memory if users don't understand immutability (each filter creates copy)
- Slightly slower (copy overhead) vs. mutable in-place

### Mitigations
- Document the immutability pattern clearly
- Implement lazy evaluation in backends (NumPy operations don't copy until needed)
- Provide `.select()` + `.where()` for efficient multi-step filtering

## Evidence from PSTH Validation

**PSTH vertical slice (examples/01_basic_psth.py) validated immutability:**

```python
query = Query(...)           # Immutable
dataset = dataset_from_session(session, query)  # New immutable object
aligned = dataset.with_alignment(alignment)     # New immutable object
epochs = aligned.get_epochs(...)                # New immutable object
result = result_from_psth_analysis(...)         # New immutable object
figure = figure_from_result(result, ...)        # New mutable object (only exception)
```

No line modified a prior object. All operations created new objects.

**Contract check:** SC-001 (Raw Data Immutability) ✓ PASSED

## Revisit Criteria

This decision should be revisited only if:
1. Immutability prevents essential features
2. Memory constraints require mutable-in-place operations
3. Three independent analyses demonstrate that lazy evaluation isn't sufficient

Otherwise: **Freeze for v1.0**.

## References

- SC-001: Raw Data Immutability (contracts.md)
- SW-001: Public Objects Immutable (contracts.md)
- Pattern: xarray.Dataset (immutable by pattern)
- Pattern: pandas.DataFrame (immutable by pattern)
