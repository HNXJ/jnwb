"""
jnwb Ontology: Core Scientific Objects

Frozen public API. These objects define the scientific data model.

All except ``Figure`` are ``frozen`` dataclasses. ``frozen`` prevents *rebinding* an
attribute, not mutation of an object an attribute points at: ``dataset.sessions`` is a
``list`` and ``dataset.sessions.append(...)`` succeeds. Treat the contained lists, dicts
and DataFrames as read-only; the ``frozen`` flag cannot enforce it for you.

Core objects:
- Query: data selection rules
- Dataset: aggregated query result
- Alignment: reference frame for epochs
- EpochCollection: filtered trials
- Question: scientific hypothesis
- Preflight: the outcome of ``preflight(question)``, checked before an analysis runs
- Result: analysis output with statistics
- Interpretation: meaning and claims
- Figure: visualization

"""

import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union, ClassVar, Tuple

import pandas as pd


def _running_jnwb() -> Dict[str, str]:
    """The version and location of the jnwb that is executing, read at construction.

    Not the caller's claim about it. Both imports are taken here rather than at module
    scope: `jnwb/__init__.py` imports this module, and `tests/test_ontology.py` holds
    this module to importing only what it uses at the top level. By the time anything
    constructs a ``Provenance`` the package is in ``sys.modules``.
    """
    from pathlib import Path

    import jnwb

    return {"version": jnwb.__version__, "path": str(Path(jnwb.__file__).parent)}


@dataclass(frozen=True)
class Provenance:
    """
    Execution context and metadata.

    Captures: software version, backend, timestamp, seed, parameters.
    Part of every Result. Immutable.

    Two of the fields are observed rather than supplied. ``jnwb_version`` and
    ``jnwb_path`` are read from the package that is executing, are ``init=False``, and
    cannot be passed to the constructor -- a record cannot claim an implementation that
    did not run. ``software_version`` remains the caller's own statement, which is not
    the same fact: nothing stops it naming a version that never executed, and when the
    two disagree the disagreement is now in the record instead of hidden behind it.

    ``jnwb_path`` is there because a version cannot identify an implementation on its
    own. An editable install of a development tree and a release in ``site-packages``
    report a version the same way, and they are routinely different code.
    """
    software_version: str
    backend: str  # "numpy", "jax", "dask", etc.
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    random_seed: Optional[int] = None
    git_commit: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    jnwb_version: str = field(init=False,
                              default_factory=lambda: _running_jnwb()["version"])
    jnwb_path: str = field(init=False,
                           default_factory=lambda: _running_jnwb()["path"])

    @property
    def version_claim_matches_execution(self) -> bool:
        """Whether the caller's ``software_version`` names the jnwb that ran."""
        return self.software_version == self.jnwb_version

    def to_dict(self) -> Dict:
        return {
            'software_version': self.software_version,
            'backend': self.backend,
            'timestamp': self.timestamp,
            'random_seed': self.random_seed,
            'git_commit': self.git_commit,
            'parameters': self.parameters,
            'environment': self.environment,
            'jnwb_version': self.jnwb_version,
            'jnwb_path': self.jnwb_path,
        }


@dataclass(frozen=True)
class Lineage:
    """
    Artifact dependencies: where did this come from?

    Traces: Session → Dataset → EpochCollection → Result
    Immutable. Every transform creates a new lineage node.
    """
    source_type: str  # "Session", "Dataset", "EpochCollection", etc.
    source_id: str    # session ID, dataset hash, etc.
    parents: List[str] = field(default_factory=list)  # IDs of parent artifacts
    operation: str = ""  # "filter", "extract_epochs", "compute_psth", etc.

    def to_dict(self) -> Dict:
        return {
            'source_type': self.source_type,
            'source_id': self.source_id,
            'parents': self.parents,
            'operation': self.operation,
        }


@dataclass(frozen=True)
class Query:
    """
    Data selection rules: what subset of data?

    Declarative specification of which sessions, areas, conditions.
    Does NOT execute itself. Immutable.

    Scientific Contracts:
    - SC-001: Query never modifies Sessions
    - SC-005: Trial identity preserved in Query result
    """
    sessions: Union[str, List[str]] = "all"
    areas: Optional[List[str]] = None
    units: Optional[List[int]] = None
    """Unit IDs to select, matched against the raw units-table row position
    (as dataset_from_session does). The 'unit_id' DataFrame column is a
    per-probe kilosort id renamed from cluster_id and repeats within a session."""
    correct_only: bool = True
    exclude_overlap: bool = False

    def __hash__(self):
        """Enable Query as dict key (e.g., for caching)."""
        sessions_str = str(self.sessions) if isinstance(self.sessions, str) else tuple(self.sessions)
        areas_str = tuple(self.areas) if self.areas else ()
        units_str = tuple(self.units) if self.units else ()
        return hash((sessions_str, areas_str, units_str, self.correct_only, self.exclude_overlap))

    def to_dict(self) -> Dict:
        return {
            'sessions': self.sessions,
            'areas': self.areas,
            'units': self.units,
            'correct_only': self.correct_only,
            'exclude_overlap': self.exclude_overlap,
        }


@dataclass(frozen=True)
class Alignment:
    """
    Reference frame for time-series data.

    Semantic labeling: where is time=0?
    Examples: stimulus_onset_relative, reward_aligned, fixation_aligned

    Scientific Contracts:
    - SC-003: Alignment never modifies timestamps
    - Alignment only relabels origin; data is unchanged
    """
    name: str  # e.g., "stimulus_onset", "reward", "fixation"
    reference_event: str  # e.g., "stimulus_onset", "trial_start"
    phase_number: Optional[int] = None  # for stimulus-phase-relative alignment

    def __hash__(self):
        return hash((self.name, self.reference_event, self.phase_number))

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'reference_event': self.reference_event,
            'phase_number': self.phase_number,
        }


@dataclass(frozen=True)
class Dataset:
    """
    Aggregated query result: immutable collection of data.

    Created from: Query.execute(sessions)
    Contains: spike times, LFP, metadata, aggregated across sessions

    Scientific Contracts:
    - SC-001: Raw data immutable (Dataset never modifies signals)
    - SC-005: Trial identity preserved

    Software Contracts:
    - SW-001: Dataset immutable (filtering returns new Dataset)
    - SW-002: Backend-independent (users don't see NumPy/JAX)
    """
    query: Query
    sessions: List[str]
    units: pd.DataFrame
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        """Enable Dataset as dict key."""
        return hash((self.query, tuple(self.sessions)))

    def __eq__(self, other: Any) -> bool:
        """Compare every field, comparing ``units`` with ``DataFrame.equals``.

        The dataclass-generated ``__eq__`` compared the field tuples, which evaluates
        ``units_a == units_b`` to a DataFrame and then takes its truth value:
        ``ValueError: The truth value of a DataFrame is ambiguous``. That made the dict
        key above unusable, because a dict consults ``__eq__`` on every hash collision --
        including the collision between a key and an equal copy of itself.

        Equality is finer than the hash (which uses ``query`` and ``sessions`` only),
        which is the direction the hash/eq contract requires.
        """
        if other.__class__ is not self.__class__:
            return NotImplemented
        return (
            self.query == other.query
            and self.sessions == other.sessions
            and self.units.equals(other.units)
            and self.metadata == other.metadata
        )

    def with_alignment(self, alignment: Alignment) -> "AlignedDataset":
        """Return new AlignedDataset pairing this Dataset with an Alignment (pure relabeling,
        no data modification)."""
        return AlignedDataset(dataset=self, alignment=alignment)


@dataclass(frozen=True)
class AlignedDataset:
    """
    Dataset with explicit Alignment.

    Separates: what data (Dataset) from how-to-interpret-time (Alignment)
    Immutable. Created by Dataset.with_alignment().
    """
    dataset: Dataset
    alignment: Alignment


@dataclass(frozen=True)
class EpochCollection:
    """
    Filtered set of trials: immutable.

    Created by: a project-specific factory that filters trial-level epoch data by condition
    and phase. Constructing this requires a real trial-timing source (a session/recording
    object), which the generic ontology objects above intentionally do not carry.
    Contains: epoch times, condition metadata, trial indices

    Scientific Contracts:
    - SC-002: Inferential unit explicit (knows what was filtered)
    - SC-005: Trial identity preserved (can trace back to source)
    """
    aligned_dataset: AlignedDataset
    condition: str
    phase: Optional[int]
    correct_only: bool
    epochs_df: pd.DataFrame  # start_time, stop_time, trial_num, etc.

    def __len__(self):
        return len(self.epochs_df)

    def __eq__(self, other: Any) -> bool:
        """Compare every field, comparing ``epochs_df`` with ``DataFrame.equals``.

        Without this, ``a == b`` raised ``ValueError: The truth value of a DataFrame is
        ambiguous`` -- two epoch collections could not be compared at all. This object
        stays unhashable: it carries a DataFrame, and there is no identifying subset of
        fields to hash it by, unlike ``Dataset``.
        """
        if other.__class__ is not self.__class__:
            return NotImplemented
        return (
            self.aligned_dataset == other.aligned_dataset
            and self.condition == other.condition
            and self.phase == other.phase
            and self.correct_only == other.correct_only
            and self.epochs_df.equals(other.epochs_df)
        )

    def to_dict(self) -> Dict:
        return {
            'condition': self.condition,
            'phase': self.phase,
            'correct_only': self.correct_only,
            'n_epochs': len(self.epochs_df),
        }


@dataclass(frozen=True)
class Question:
    """
    Scientific hypothesis: what are we asking?

    Pure data. No methods. No execution.
    Frozen dataclass: immutable, serializable, hashable.

    The fields after ``metadata`` describe a planned analysis for ``preflight`` and all
    default to empty, so a ``Question`` built from the first five fields alone is unchanged.
    ``hypothesis`` states the goal.

    - ``signal_units``: the unit of each signal, keyed by the name in ``signals``
      (``{"lfp": "V"}``). Distinct from ``inference_unit``, the unit of inference.
    - ``data``, ``paradigm``, ``verification_plan``: free-text descriptions.
    - ``axes``: the axis order of each signal, keyed by signal name (``{"lfp": "trials x time"}``).
    - ``conditions``, ``required_skills``: names.
    - ``unsupported_inference``: set by the caller when the question asks for an inference no
      operation supports; the text is the reason. ``preflight`` then declines.
    - ``non_identifiable``: set by the caller when the result cannot be identified from these
      inputs; the text is the reason. ``preflight`` then reports a failure.

    Scientific Contracts:
    - SC-002: Inferential unit must be explicit
    """
    hypothesis: str
    signals: List[str]  # e.g., ["spike_times"], ["lfp"], ["spike_times", "lfp"]
    contrast: str  # e.g., "baseline vs response", "AAAB vs AAXB"
    inference_unit: str  # "unit", "session", "subject"
    metadata: Dict[str, Any] = field(default_factory=dict)
    signal_units: Dict[str, str] = field(default_factory=dict)
    data: str = ""
    paradigm: str = ""
    axes: Dict[str, str] = field(default_factory=dict)
    conditions: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    verification_plan: str = ""
    unsupported_inference: str = ""
    non_identifiable: str = ""

    def __hash__(self):
        """Enable Question as cache key."""
        return hash((
            self.hypothesis,
            tuple(self.signals),
            self.contrast,
            self.inference_unit,
        ))

    def to_dict(self) -> Dict:
        return {
            'hypothesis': self.hypothesis,
            'signals': self.signals,
            'contrast': self.contrast,
            'inference_unit': self.inference_unit,
            'metadata': self.metadata,
            'signal_units': self.signal_units,
            'data': self.data,
            'paradigm': self.paradigm,
            'axes': self.axes,
            'conditions': self.conditions,
            'required_skills': self.required_skills,
            'verification_plan': self.verification_plan,
            'unsupported_inference': self.unsupported_inference,
            'non_identifiable': self.non_identifiable,
        }


@dataclass(frozen=True)
class Preflight:
    """
    The outcome of checking a planned analysis before it runs.

    One of four outcomes, with the reason and, for a request, the inputs it needs:

    - ``"supported"``: the operations exist and the inputs are present; compose and execute.
    - ``"request"``: an input is missing; ``missing`` names each one.
    - ``"failure"``: the result would not be identifiable from these inputs.
    - ``"decline"``: the inference is one no operation supports.

    Every field is plain data, so a script can score outcomes from the object or from
    ``to_dict()`` alone. ``missing`` is non-empty exactly when ``outcome`` is ``"request"``.
    """
    outcome: str
    reason: str
    missing: Tuple[str, ...] = ()

    OUTCOMES: ClassVar[Tuple[str, ...]] = ("supported", "request", "failure", "decline")

    def __post_init__(self):
        if self.outcome not in self.OUTCOMES:
            raise ValueError(f"outcome={self.outcome!r} is not one of {self.OUTCOMES}")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        missing = tuple(self.missing)
        if not all(isinstance(m, str) and m.strip() for m in missing):
            raise ValueError(f"missing must hold non-empty strings, got {missing!r}")
        if (self.outcome == "request") != bool(missing):
            raise ValueError(
                "missing is non-empty exactly when outcome is 'request'; "
                f"got outcome={self.outcome!r}, missing={missing!r}"
            )
        object.__setattr__(self, "missing", missing)

    def to_dict(self) -> Dict:
        return {
            'outcome': self.outcome,
            'reason': self.reason,
            'missing': list(self.missing),
        }


def _stated(value: Any) -> bool:
    """Whether a field carries content: a non-blank string or a non-empty collection."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


#: The four inputs without which no analysis can be composed.
_PREFLIGHT_REQUIRED: Tuple[str, ...] = ("signals", "signal_units", "contrast", "inference_unit")
#: Inputs a plan should state; their absence is reported in the reason and requests nothing.
_PREFLIGHT_OPTIONAL: Tuple[str, ...] = (
    "hypothesis", "data", "paradigm", "axes", "conditions", "required_skills",
    "verification_plan",
)


def preflight(question: Question) -> Preflight:
    """Check a planned analysis before it runs and return one of the four outcomes.

    The checks run in this order, and the first that applies decides the outcome:

    1. ``"decline"`` when ``question.unsupported_inference`` is stated. The caller declares
       the unsupported inference; jnwb holds no list of claims.
    2. ``"request"`` when any of ``signals``, ``signal_units``, ``contrast`` or
       ``inference_unit`` is empty, or a signal in ``signals`` has no entry in
       ``signal_units``. ``missing`` names each: a field by its name, an absent unit as
       ``signal_units[<repr of the signal>]``, once per signal.
    3. ``"failure"`` when ``question.non_identifiable`` is stated: the caller declares
       that the result cannot be identified from these inputs.
    4. ``"supported"`` otherwise.

    The reason carries the caller's text for a decline or a failure, and ends by naming
    the optional fields left empty (``hypothesis``, ``data``, ``paradigm``, ``axes``,
    ``conditions``, ``required_skills``, ``verification_plan``). An empty optional field
    never changes the outcome.

    Parameters
    ----------
    question : Question
        The planned analysis.

    Returns
    -------
    Preflight
        ``outcome``, ``reason`` and ``missing``, all plain data.

    Raises
    ------
    TypeError
        If ``question`` is not a ``Question``, ``signals`` is a string, ``signal_units`` is
        not a dict, or ``unsupported_inference`` or ``non_identifiable`` is not a string.
    """
    if not isinstance(question, Question):
        raise TypeError(f"preflight takes a Question, got {type(question).__name__}")
    if not isinstance(question.signal_units, dict):
        raise TypeError(
            "signal_units maps each signal name to its unit, e.g. {'lfp': 'V'}; "
            f"got {type(question.signal_units).__name__}"
        )
    if isinstance(question.signals, str):
        raise TypeError(f"signals is a list of signal names, e.g. ['lfp']; got the string {question.signals!r}")
    for name in ("unsupported_inference", "non_identifiable"):
        if not isinstance(getattr(question, name), str):
            raise TypeError(f"{name} is a string; got {type(getattr(question, name)).__name__}")

    absent = [name for name in _PREFLIGHT_OPTIONAL if not _stated(getattr(question, name))]
    not_stated = f" Not stated: {', '.join(absent)}." if absent else ""

    if _stated(question.unsupported_inference):
        return Preflight(
            outcome="decline",
            reason=f"Unsupported inference: {question.unsupported_inference.strip().rstrip('.')}.{not_stated}",
        )

    missing = [name for name in _PREFLIGHT_REQUIRED if not _stated(getattr(question, name))]
    if _stated(question.signals) and _stated(question.signal_units):
        missing += [
            f"signal_units[{signal!r}]"
            for signal in dict.fromkeys(question.signals)
            if not _stated(question.signal_units.get(signal))
        ]
    if missing:
        return Preflight(
            outcome="request",
            reason=f"Required inputs are missing: {', '.join(missing)}.{not_stated}",
            missing=tuple(missing),
        )

    if _stated(question.non_identifiable):
        return Preflight(
            outcome="failure",
            reason=f"Not identifiable: {question.non_identifiable.strip().rstrip('.')}.{not_stated}",
        )

    return Preflight(
        outcome="supported",
        reason=f"Every required input is present.{not_stated}",
    )


@dataclass(frozen=True)
class Result:
    """
    Analysis output: statistics, provenance, lineage.

    Created by: Analysis.compute(AnalysisPlan)
    Immutable. Results are facts.

    Software Contracts:
    - SW-001: Result immutable (statistics don't change)
    - SW-004: ``to_dict()`` returns a plain nested ``dict``. Whether that dict is
      *JSON*-serializable depends on what the caller put in ``statistics``, which is
      ``Dict[str, Any]`` and in this package normally holds NumPy values:
      ``json.dumps(result.to_dict())`` raises ``TypeError: Object of type ndarray is not
      JSON serializable``. Pass a ``default=`` hook, e.g.
      ``json.dumps(result.to_dict(), default=lambda o: o.tolist())``. ``to_dict`` does not
      convert values, so nothing is silently coerced or rounded on the way out.
    """
    question: Question
    statistics: Dict[str, Any]
    provenance: Provenance
    lineage: Lineage

    def to_dict(self) -> Dict:
        return {
            'question': self.question.to_dict(),
            'statistics': self.statistics,
            'provenance': self.provenance.to_dict(),
            'lineage': self.lineage.to_dict(),
        }


@dataclass(frozen=True)
class Interpretation:
    """
    Meaning and claims: what does the result mean?

    Separates: measured evidence (Result) from scientific argument (Interpretation)
    Immutable. Built after inspecting a Result, never from one automatically.

    Scientific Contracts:
    - SC-004: Interpretation never modifies Result
    """
    claim: str
    confidence: str  # "high", "moderate", "low"
    alternative_explanations: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'claim': self.claim,
            'confidence': self.confidence,
            'alternative_explanations': self.alternative_explanations,
            'limitations': self.limitations,
            'metadata': self.metadata,
        }


@dataclass
class Figure:
    """
    Visualization: rendering of Result + Interpretation.

    MUTABLE (only public API object that is mutable).
    Styling and layout can change; underlying data cannot.

    This object carries figure metadata (title, axes_data, layout) as plain dicts, not a bound
    renderer -- it has nothing to draw with. Actual PNG/PDF/SVG rendering happens where the plot
    is built (e.g. matplotlib calls in a project's factory functions, which call `fig.savefig`
    directly); this object is what gets attached to that Result afterward, not what does the
    rendering.

    Software Contracts:
    - SW-004: Figure serializable (`to_dict()` -- JSON-style metadata export)
    """
    result: Result
    interpretation: Interpretation
    title: str = ""
    axes_data: Dict[str, Any] = field(default_factory=dict)
    layout: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'result': self.result.to_dict(),
            'interpretation': self.interpretation.to_dict(),
            'title': self.title,
        }


# Deprecated factory functions.
#
# create_dataset_from_query and create_epochs are intentionally absent here: both need a real
# NWB/trial-timing data source (an open session/recording object) that these generic ontology
# objects do not carry, so a generic implementation would have nothing to read from. Projects
# provide their own dataset/epoch factories once they have a concrete data source to wire in.
#
# The three below forward their arguments to the constructor of the same name and add nothing:
# `create_result(q, s, p, l) == Result(q, s, p, l)` for every input. They were never in
# `__all__`. Deprecated in 0.2.5 rather than removed, so callers have a path; call the
# dataclass directly. `create_aligned_dataset` additionally duplicates `Dataset.with_alignment`,
# which is the documented route and is not deprecated.


def _deprecated_factory(old: str, new: str) -> None:
    warnings.warn(
        f"{old} is deprecated and will be removed in a future release; it forwards to "
        f"{new} and adds nothing. Call {new} directly.",
        DeprecationWarning,
        stacklevel=3,
    )


def create_aligned_dataset(dataset: Dataset, alignment: Alignment) -> AlignedDataset:
    """Deprecated. Use ``Dataset.with_alignment(alignment)`` or ``AlignedDataset(...)``."""
    _deprecated_factory("create_aligned_dataset", "Dataset.with_alignment")
    return AlignedDataset(dataset=dataset, alignment=alignment)


def create_result(question: Question, statistics: Dict[str, Any],
                  provenance: Provenance, lineage: Lineage) -> Result:
    """Deprecated. Use ``Result(...)``."""
    _deprecated_factory("create_result", "Result")
    return Result(
        question=question,
        statistics=statistics,
        provenance=provenance,
        lineage=lineage,
    )


def create_figure(result: Result, interpretation: Interpretation,
                  title: str = "") -> Figure:
    """Deprecated. Use ``Figure(...)``."""
    _deprecated_factory("create_figure", "Figure")
    return Figure(
        result=result,
        interpretation=interpretation,
        title=title,
    )


__all__ = [
    'Query',
    'Dataset',
    'AlignedDataset',
    'Alignment',
    'EpochCollection',
    'Question',
    'Preflight',
    'preflight',
    'Result',
    'Interpretation',
    'Figure',
    'Provenance',
    'Lineage',
]
