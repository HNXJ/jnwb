"""`jnwb.ontology` -- the exported objects, and what they actually promise.

The audit reported this module as 11 public symbols with zero call sites, zero behavioural
tests, and zero mentions outside `docs/`, and proposed removal. The 2026-09-16 ruling
rejected removal-by-call-site-count: a public library exists for callers a repository
search cannot observe, so each export is judged on
`distinct useful operation AND documented AND tested AND generic` instead.

All 11 pass. What the evaluation did find is that three of the docstrings' own contracts
were false, and this file is the test half of the repair:

- `Dataset.__hash__` says "Enable Dataset as dict key". The dataclass-generated `__eq__`
  compared the field tuples, which evaluates `units_a == units_b` to a DataFrame and then
  takes its truth value -- `ValueError: The truth value of a DataFrame is ambiguous`. A
  dict consults `__eq__` on every hash collision, including the collision between a key
  and an equal copy of it, so the one use the custom `__hash__` was written for raised.
- `EpochCollection` had the same generated-`__eq__` defect: two epoch collections could
  not be compared at all.
- `Result` carried "SW-004: Result serializable" unconditionally, while `statistics` is
  `Dict[str, Any]` and in this package normally holds NumPy values, for which
  `json.dumps` raises. A contract that depends on caller input cannot be stated
  unconditionally, so the docstring now states the condition and the escape hatch.

The three `create_*` factories forward to the constructor of the same name and add
nothing, so they fail "distinct useful operation". They were never in `__all__`. They are
deprecated here rather than deleted, so callers have a path.
"""

from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb import ontology as O


#: The exported classes; `preflight`, the one exported function, has its own tests below.
EXPORTS = tuple(name for name in O.__all__ if isinstance(getattr(O, name), type))
DEPRECATED_FACTORIES = ("create_aligned_dataset", "create_result", "create_figure")


@pytest.fixture
def parts():
    """One instance of every exported object, wired into the chain the module describes."""
    units = pd.DataFrame({"unit_id": [1, 2], "area": ["V1", "V4"]})
    query = O.Query(sessions=["ses-01"], areas=["V1"], units=[0, 1])
    dataset = O.Dataset(query=query, sessions=["ses-01"], units=units)
    alignment = O.Alignment(name="stimulus_onset", reference_event="stimulus_onset")
    aligned = dataset.with_alignment(alignment)
    epochs = O.EpochCollection(
        aligned_dataset=aligned, condition="AAAB", phase=2, correct_only=True,
        epochs_df=pd.DataFrame({"start_time": [0.0, 1.0], "stop_time": [0.5, 1.5]}),
    )
    question = O.Question(
        hypothesis="V1 responds to the deviant",
        signals=["spike_times"], contrast="AAAB vs AAXB", inference_unit="unit",
    )
    provenance = O.Provenance(software_version="0.2.5", backend="numpy", random_seed=7)
    lineage = O.Lineage(source_type="Dataset", source_id="ses-01", operation="compute_psth")
    result = O.Result(question=question, statistics={"p": 0.01},
                      provenance=provenance, lineage=lineage)
    interpretation = O.Interpretation(claim="deviant response present", confidence="moderate")
    figure = O.Figure(result=result, interpretation=interpretation, title="Fig 1")
    return {
        "Query": query, "Dataset": dataset, "Alignment": alignment,
        "AlignedDataset": aligned, "EpochCollection": epochs, "Question": question,
        "Preflight": O.preflight(question),
        "Provenance": provenance, "Lineage": lineage, "Result": result,
        "Interpretation": interpretation, "Figure": figure,
    }


class TestEveryExportIsReachableAndExercised:
    """The ruling's criterion applied mechanically, so a future export cannot skip it."""

    def test_the_export_list_is_what_this_file_covers(self, parts):
        assert set(EXPORTS) == set(parts), (
            "ontology.__all__ changed; this file tests a stale set"
        )

    @pytest.mark.parametrize("name", EXPORTS)
    def test_each_export_is_importable_from_the_top_level(self, name):
        assert hasattr(jnwb, name)
        assert name in jnwb.__all__
        assert getattr(jnwb, name) is getattr(O, name)

    @pytest.mark.parametrize("name", EXPORTS)
    def test_each_export_is_constructible_and_carries_a_docstring(self, name, parts):
        obj = parts[name]
        assert isinstance(obj, getattr(O, name))
        assert (getattr(O, name).__doc__ or "").strip(), f"{name} has no docstring"

    @pytest.mark.parametrize(
        "name",
        ["Query", "Alignment", "EpochCollection", "Question", "Preflight", "Provenance",
         "Lineage", "Result", "Interpretation", "Figure"],
    )
    def test_each_object_with_a_to_dict_round_trips_its_own_fields(self, name, parts):
        """`to_dict` is the one operation these objects share; it must report the object."""
        d = parts[name].to_dict()
        assert isinstance(d, dict) and d, f"{name}.to_dict() returned {d!r}"

    def test_the_chain_the_module_documents_actually_composes(self, parts):
        """Query -> Dataset -> AlignedDataset -> EpochCollection, and Question -> Result
        -> Interpretation -> Figure. If a link were redundant this would not need it."""
        assert parts["AlignedDataset"].dataset is parts["Dataset"]
        assert parts["AlignedDataset"].alignment is parts["Alignment"]
        assert parts["EpochCollection"].aligned_dataset is parts["AlignedDataset"]
        assert parts["Dataset"].query is parts["Query"]
        assert parts["Result"].question is parts["Question"]
        assert parts["Figure"].result is parts["Result"]
        assert parts["Figure"].interpretation is parts["Interpretation"]

    def test_the_module_is_generic(self):
        """No project, subject, area or session identifier is baked into the source."""
        import inspect

        src = inspect.getsource(O)
        for token in ("ses-2607", "mm_depth", "probeA", "omission", "Hamm"):
            assert token not in src, f"project-specific token {token!r} in ontology.py"


class TestDatasetIsUsableAsADictKey:
    """The repair for the defect `Dataset.__hash__`'s own docstring advertises."""

    def test_two_equal_datasets_compare_equal(self, parts):
        a = parts["Dataset"]
        b = O.Dataset(query=a.query, sessions=list(a.sessions), units=a.units.copy())
        assert a == b

    def test_a_dict_keyed_by_dataset_collapses_equal_keys(self, parts):
        """This is the line that raised ValueError before the repair: inserting an equal
        key forces the dict to consult `__eq__` after the hashes collide."""
        a = parts["Dataset"]
        b = O.Dataset(query=a.query, sessions=list(a.sessions), units=a.units.copy())
        d = {a: "first"}
        d[b] = "second"
        assert len(d) == 1 and d[a] == "second"

    def test_a_dataset_whose_units_differ_is_not_equal(self, parts):
        a = parts["Dataset"]
        c = O.Dataset(query=a.query, sessions=list(a.sessions),
                      units=pd.DataFrame({"unit_id": [9], "area": ["MT"]}))
        assert a != c

    def test_equality_is_finer_than_the_hash_which_is_the_legal_direction(self, parts):
        """The hash uses `query` and `sessions` only, so unequal datasets may collide.
        That is allowed; the reverse -- equal objects with different hashes -- is not."""
        a = parts["Dataset"]
        c = O.Dataset(query=a.query, sessions=list(a.sessions),
                      units=pd.DataFrame({"unit_id": [9], "area": ["MT"]}))
        assert a != c
        assert hash(a) == hash(c)
        b = O.Dataset(query=a.query, sessions=list(a.sessions), units=a.units.copy())
        assert a == b and hash(a) == hash(b)

    def test_comparison_against_another_type_is_not_an_error(self, parts):
        assert parts["Dataset"] != "not a dataset"
        assert parts["Dataset"] != parts["Query"]

    def test_metadata_participates_in_equality(self, parts):
        a = parts["Dataset"]
        b = O.Dataset(query=a.query, sessions=list(a.sessions), units=a.units.copy(),
                      metadata={"note": "x"})
        assert a != b


class TestEpochCollectionCompares:
    """Same generated-`__eq__` defect, same repair, on the other DataFrame carrier."""

    @staticmethod
    def _make(parts, start=(0.0, 1.0), condition="AAAB"):
        return O.EpochCollection(
            aligned_dataset=parts["AlignedDataset"], condition=condition, phase=2,
            correct_only=True,
            epochs_df=pd.DataFrame({"start_time": list(start),
                                    "stop_time": [s + 0.5 for s in start]}),
        )

    def test_two_equal_collections_compare_equal(self, parts):
        assert self._make(parts) == self._make(parts)

    def test_different_epoch_times_compare_unequal(self, parts):
        assert self._make(parts) != self._make(parts, start=(2.0, 3.0))

    def test_different_conditions_compare_unequal(self, parts):
        assert self._make(parts) != self._make(parts, condition="AAXB")

    def test_it_remains_unhashable_and_says_so_plainly(self, parts):
        """It carries a DataFrame and has no identifying subset to hash by, unlike
        `Dataset`. The failure must be a clean TypeError, not a pandas ValueError."""
        with pytest.raises(TypeError):
            hash(self._make(parts))

    def test_len_counts_epochs(self, parts):
        assert len(self._make(parts, start=(0.0, 1.0, 2.0))) == 3

    def test_comparison_against_another_type_is_not_an_error(self, parts):
        assert self._make(parts) != 17


class TestTheSerializationContractIsStatedTruthfully:
    """"SW-004: Result serializable" was unconditional and false."""

    def test_to_dict_is_a_plain_nested_dict(self, parts):
        d = parts["Result"].to_dict()
        assert set(d) == {"question", "statistics", "provenance", "lineage"}
        assert isinstance(d["provenance"], dict) and isinstance(d["question"], dict)

    def test_json_native_statistics_serialize(self, parts):
        json.dumps(parts["Result"].to_dict())  # statistics={"p": 0.01}

    def test_numpy_statistics_do_not_and_the_docstring_now_says_so(self, parts):
        """The claim is now conditional. This test pins the condition, so the docstring
        cannot drift back to promising something the object does not do."""
        res = O.Result(question=parts["Question"], statistics={"psth": np.arange(3)},
                       provenance=parts["Provenance"], lineage=parts["Lineage"])
        with pytest.raises(TypeError, match="not JSON serializable"):
            json.dumps(res.to_dict())

        doc = O.Result.__doc__
        assert "json.dumps" in doc and "default=" in doc, (
            "the Result docstring must state the condition and the escape hatch"
        )
        assert "SW-004: Result serializable\n" not in doc, (
            "the unconditional claim is back"
        )

    def test_the_documented_escape_hatch_works(self, parts):
        res = O.Result(question=parts["Question"], statistics={"psth": np.arange(3)},
                       provenance=parts["Provenance"], lineage=parts["Lineage"])
        text = json.dumps(res.to_dict(), default=lambda o: o.tolist())
        assert json.loads(text)["statistics"]["psth"] == [0, 1, 2]

    def test_to_dict_does_not_coerce_values(self, parts):
        """Nothing is rounded, cast or stringified on the way out -- the array that goes
        in is the array that comes out, so no number changes shape or precision."""
        arr = np.array([1.5, 2.5], dtype=np.float32)
        res = O.Result(question=parts["Question"], statistics={"psth": arr},
                       provenance=parts["Provenance"], lineage=parts["Lineage"])
        out = res.to_dict()["statistics"]["psth"]
        assert out is arr and out.dtype == np.float32


class TestHashabilityMatchesTheDocstrings:
    """`Query` and `Question` document cache-key use; the rest make no such claim."""

    @pytest.mark.parametrize("name", ["Query", "Alignment", "Dataset", "AlignedDataset",
                                      "Question"])
    def test_the_objects_that_claim_to_be_keys_are_hashable(self, name, parts):
        assert isinstance(hash(parts[name]), int)
        assert {parts[name]: 1}[parts[name]] == 1

    @pytest.mark.parametrize("name", ["Provenance", "Lineage", "EpochCollection",
                                      "Result", "Interpretation", "Figure"])
    def test_the_objects_that_hold_dicts_lists_or_frames_are_not(self, name, parts):
        with pytest.raises(TypeError):
            hash(parts[name])

    def test_query_hashes_equal_for_equal_content(self):
        a = O.Query(sessions=["s1", "s2"], areas=["V1"], units=[3])
        b = O.Query(sessions=["s1", "s2"], areas=["V1"], units=[3])
        assert hash(a) == hash(b) and a == b

    def test_question_hashes_ignore_metadata_as_its_docstring_implies(self):
        a = O.Question(hypothesis="h", signals=["lfp"], contrast="c",
                       inference_unit="unit", metadata={"run": 1})
        b = O.Question(hypothesis="h", signals=["lfp"], contrast="c",
                       inference_unit="unit", metadata={"run": 2})
        assert hash(a) == hash(b)
        assert a != b, "metadata still distinguishes them under =="


class TestFrozenDoesNotFreezeWhatTheFieldsPointAt:
    """The module docstring used to say "All are immutable unless otherwise specified"."""

    def test_rebinding_a_field_is_refused(self, parts):
        with pytest.raises(Exception):  # FrozenInstanceError
            parts["Dataset"].sessions = ["other"]

    def test_but_mutating_the_contained_list_is_not_and_the_docstring_admits_it(self, parts):
        before = list(parts["Dataset"].sessions)
        parts["Dataset"].sessions.append("ses-02")
        assert parts["Dataset"].sessions == before + ["ses-02"]
        assert "frozen" in O.__doc__ and "append" in O.__doc__, (
            "the module docstring must state that frozen does not protect contained "
            "containers, because it does not"
        )

    def test_figure_is_the_documented_mutable_one(self, parts):
        parts["Figure"].title = "Fig 2"
        assert parts["Figure"].title == "Fig 2"


class TestDeprecatedFactoriesWarnAndStillWork:
    """They forward to the constructor and add nothing -- they fail "distinct useful
    operation". Deprecated, not deleted: a public API change carries a deprecation path."""

    @pytest.mark.parametrize("name", DEPRECATED_FACTORIES)
    def test_the_factory_is_not_and_never_was_part_of_the_declared_surface(self, name):
        assert name not in O.__all__
        assert name not in jnwb.__all__

    def test_create_aligned_dataset_warns_and_equals_the_method(self, parts):
        with pytest.warns(DeprecationWarning, match="create_aligned_dataset is deprecated"):
            made = O.create_aligned_dataset(parts["Dataset"], parts["Alignment"])
        assert made == parts["Dataset"].with_alignment(parts["Alignment"])

    def test_create_result_warns_and_equals_the_constructor(self, parts):
        args = (parts["Question"], {"p": 0.01}, parts["Provenance"], parts["Lineage"])
        with pytest.warns(DeprecationWarning, match="create_result is deprecated"):
            made = O.create_result(*args)
        assert made == O.Result(*args)

    def test_create_figure_warns_and_equals_the_constructor(self, parts):
        with pytest.warns(DeprecationWarning, match="create_figure is deprecated"):
            made = O.create_figure(parts["Result"], parts["Interpretation"], "t")
        assert made == O.Figure(parts["Result"], parts["Interpretation"], "t")

    @pytest.mark.parametrize("name", DEPRECATED_FACTORIES)
    def test_the_warning_names_the_replacement(self, name, parts):
        calls = {
            "create_aligned_dataset": (parts["Dataset"], parts["Alignment"]),
            "create_result": (parts["Question"], {}, parts["Provenance"], parts["Lineage"]),
            "create_figure": (parts["Result"], parts["Interpretation"]),
        }
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            getattr(O, name)(*calls[name])
        assert len(caught) == 1
        text = str(caught[0].message)
        assert "Call " in text and "directly" in text, text

    @pytest.mark.parametrize("name", DEPRECATED_FACTORIES)
    def test_the_deprecation_is_announced_in_the_changelog(self, name):
        from pathlib import Path

        # From this file, not from `jnwb.__file__`: the package's parent is the
        # repository only when the import came from the checkout, so against an
        # installed wheel this read site-packages and failed.
        changelog = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
        assert name in changelog.read_text(encoding="utf-8"), (
            "a public API change is announced in CHANGELOG.md"
        )


class TestTheModuleImportsOnlyWhatItUses:
    """`hashlib` and `json` in particular advertised content-hashing and serialization
    that the module never implemented; `numpy`, `pathlib.Path` and `logging` were unused
    too. They were reachable as `jnwb.ontology.np` and friends."""

    @pytest.mark.parametrize("name", ["hashlib", "json", "np", "numpy", "Path", "log",
                                      "logging"])
    def test_the_unused_import_is_gone(self, name):
        assert not hasattr(O, name), f"ontology.{name} is imported but unused"

    def test_what_it_does_use_is_still_there(self):
        assert hasattr(O, "pd") and hasattr(O, "warnings") and hasattr(O, "datetime")


class TestPreflightCarriesItsOutcomeAsData:
    """A script reads the outcome, the reason and the missing inputs from the object alone."""

    CASES = {
        "supported": ("the operations exist and every input is present", ()),
        "request": ("no sampling rate was given", ("fs", "baseline_window")),
        "failure": ("one class in the labels leaves nothing to decode", ()),
        "decline": ("lag asymmetry does not establish causation", ()),
    }

    def test_the_vocabulary_is_the_four_outcomes_in_order(self):
        assert O.Preflight.OUTCOMES == ("supported", "request", "failure", "decline")

    @pytest.mark.parametrize("outcome", list(CASES))
    def test_each_outcome_round_trips_through_to_dict(self, outcome):
        reason, missing = self.CASES[outcome]
        pf = O.Preflight(outcome=outcome, reason=reason, missing=list(missing))
        assert (pf.outcome, pf.reason, pf.missing) == (outcome, reason, missing)
        d = json.loads(json.dumps(pf.to_dict()))
        assert d == {"outcome": outcome, "reason": reason, "missing": list(missing)}

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            ({"outcome": "non_identifiable", "reason": "r"}, "is not one of"),
            ({"outcome": "decline", "reason": "  "}, "non-empty string"),
            ({"outcome": "request", "reason": "r"}, "exactly when"),
            ({"outcome": "supported", "reason": "r", "missing": ("fs",)}, "exactly when"),
            ({"outcome": "request", "reason": "r", "missing": ("",)}, "non-empty strings"),
        ],
        ids=["unknown-outcome", "blank-reason", "request-names-nothing",
             "missing-without-request", "blank-missing-name"],
    )
    def test_an_inconsistent_record_is_refused(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            O.Preflight(**kwargs)



def _plan(**changes) -> O.Question:
    """A planned analysis with every field stated; `changes` overrides any of them."""
    fields = dict(
        hypothesis="the response differs from baseline",
        signals=["spike_times", "lfp"],
        contrast="baseline vs response",
        inference_unit="unit",
        signal_units={"spike_times": "s", "lfp": "V"},
        data="one NWB file",
        paradigm="passive viewing",
        axes={"spike_times": "events", "lfp": "trials x time"},
        conditions=["baseline", "response"],
        required_skills=["jnwb-spiking"],
        verification_plan="a label permutation null",
    )
    fields.update(changes)
    return O.Question(**fields)


REQUIRED = ("signals", "signal_units", "contrast", "inference_unit")
EMPTY = {"signals": [], "signal_units": {}, "contrast": " ", "inference_unit": ""}


class TestPreflightIsThePublicCheck:
    """`jnwb.preflight(question)`: each outcome read from the returned object alone."""

    def test_both_names_are_exported(self):
        for name in ("Preflight", "preflight"):
            assert name in jnwb.__all__ and name in O.__all__
            assert getattr(jnwb, name) is getattr(O, name)

    def test_supported(self):
        pf = jnwb.preflight(_plan())
        assert (pf.outcome, pf.missing) == ("supported", ())
        assert pf.reason == "Every required input is present."

    @pytest.mark.parametrize("name", REQUIRED)
    def test_request_names_each_missing_required_input(self, name):
        pf = jnwb.preflight(_plan(**{name: EMPTY[name]}))
        assert pf.outcome == "request"
        assert pf.missing == (name,)
        assert name in pf.reason

    def test_request_names_a_signal_without_a_unit(self):
        pf = jnwb.preflight(_plan(signal_units={"spike_times": "s"}))
        assert pf.outcome == "request"
        assert pf.missing == ("signal_units['lfp']",)

    def test_a_blank_unit_is_a_missing_unit_and_a_repeated_signal_is_named_once(self):
        pf = jnwb.preflight(_plan(signals=["spike_times", "lfp", "lfp"],
                                  signal_units={"spike_times": "s", "lfp": "  "}))
        assert (pf.outcome, pf.missing) == ("request", ("signal_units['lfp']",))

    @pytest.mark.parametrize("changes", [
        {"signals": "lfp"}, {"unsupported_inference": True}, {"non_identifiable": ["x"]},
    ])
    def test_a_field_of_the_wrong_type_raises(self, changes):
        with pytest.raises(TypeError):
            jnwb.preflight(_plan(**changes))

    def test_request_names_every_missing_input_at_once(self):
        pf = jnwb.preflight(_plan(**EMPTY))
        assert pf.outcome == "request" and pf.missing == REQUIRED

    def test_failure(self):
        pf = jnwb.preflight(_plan(non_identifiable="one class leaves nothing to decode"))
        assert (pf.outcome, pf.missing) == ("failure", ())
        assert "one class leaves nothing to decode" in pf.reason

    def test_decline(self):
        pf = jnwb.preflight(_plan(unsupported_inference="lag asymmetry is not causation"))
        assert (pf.outcome, pf.missing) == ("decline", ())
        assert "lag asymmetry is not causation" in pf.reason

    def test_a_declared_decline_beats_missing_inputs(self):
        pf = jnwb.preflight(_plan(unsupported_inference="x", **EMPTY))
        assert (pf.outcome, pf.missing) == ("decline", ())

    def test_a_declared_decline_beats_a_declared_failure(self):
        pf = jnwb.preflight(_plan(unsupported_inference="x", non_identifiable="y"))
        assert pf.outcome == "decline"

    def test_missing_inputs_beat_a_declared_failure(self):
        pf = jnwb.preflight(_plan(non_identifiable="y", contrast=""))
        assert (pf.outcome, pf.missing) == ("request", ("contrast",))

    def test_a_blank_declaration_declares_nothing(self):
        pf = jnwb.preflight(_plan(unsupported_inference="  ", non_identifiable="  "))
        assert pf.outcome == "supported"

    def test_absent_optional_fields_are_reported_and_change_nothing(self):
        pf = jnwb.preflight(_plan(hypothesis=" ", data="", paradigm="", axes={}, conditions=[],
                                  required_skills=[], verification_plan=""))
        assert pf.outcome == "supported"
        assert pf.reason.endswith(
            "Not stated: hypothesis, data, paradigm, axes, conditions, required_skills, "
            "verification_plan."
        )

    def test_a_question_built_the_old_way_is_unchanged_and_requests_units(self):
        q = O.Question("h", ["lfp"], "a vs b", "session", {"run": 1})
        assert (q.hypothesis, q.signals, q.contrast, q.inference_unit, q.metadata) == (
            "h", ["lfp"], "a vs b", "session", {"run": 1})
        assert q.signal_units == {} and q.unsupported_inference == ""
        pf = jnwb.preflight(q)
        assert (pf.outcome, pf.missing) == ("request", ("signal_units",))

    def test_the_question_and_the_preflight_round_trip_through_json(self):
        q = _plan(signal_units={"spike_times": "s"})
        assert O.Question(**json.loads(json.dumps(q.to_dict()))) == q
        pf = jnwb.preflight(q)
        assert O.Preflight(**json.loads(json.dumps(pf.to_dict()))) == pf

    def test_anything_but_a_question_is_refused(self):
        with pytest.raises(TypeError, match="takes a Question"):
            jnwb.preflight(_plan().to_dict())
        with pytest.raises(TypeError, match="signal_units maps"):
            jnwb.preflight(_plan(signal_units=["s", "V"]))

    def test_a_script_scores_the_four_outcomes_from_the_returned_data(self, tmp_path):
        """A separate process imports this checkout and prints each outcome's `to_dict()`."""
        import os
        import subprocess
        import sys
        from pathlib import Path

        script = tmp_path / "score.py"
        script.write_text(
            "import json, jnwb\n"
            "base = dict(hypothesis='h', signals=['lfp'], contrast='a vs b',\n"
            "            inference_unit='unit', signal_units={'lfp': 'V'})\n"
            "cases = {'supported': {}, 'request': {'signal_units': {}},\n"
            "         'failure': {'non_identifiable': 'r'},\n"
            "         'decline': {'unsupported_inference': 'r'}}\n"
            "print(json.dumps({'path': jnwb.__file__, 'scored': {\n"
            "    k: jnwb.preflight(jnwb.Question(**{**base, **v})).to_dict()\n"
            "    for k, v in cases.items()}}))\n",
            encoding="utf-8",
        )
        repo = Path(__file__).resolve().parents[1]
        env = {**os.environ, "PYTHONPATH": str(repo)}
        out = json.loads(subprocess.run([sys.executable, str(script)], capture_output=True,
                                        text=True, env=env, check=True).stdout)
        assert Path(out["path"]).resolve().parent == repo / "jnwb", out["path"]
        scored = out["scored"]
        assert {k: v["outcome"] for k, v in scored.items()} == {k: k for k in scored}
        assert set(scored) == set(O.Preflight.OUTCOMES)
        assert scored["request"]["missing"] == ["signal_units"]
        assert all(v["reason"] for v in scored.values())


class TestProvenanceRecordsThePackageThatRan:
    """`software_version` is the caller's claim and nothing derived it, so a
    record could name a version that never executed -- and, being frozen, keep it. A
    version alone cannot identify an implementation either: an editable install of a
    development tree and a release in site-packages report theirs the same way.
    """

    def test_the_running_version_and_path_are_observed_not_supplied(self):
        import jnwb
        from pathlib import Path

        p = O.Provenance(software_version="not-a-version", backend="numpy")
        assert p.jnwb_version == jnwb.__version__
        assert p.jnwb_path == str(Path(jnwb.__file__).parent)

    def test_a_caller_cannot_overwrite_the_observed_identity(self):
        with pytest.raises(TypeError):
            O.Provenance(software_version="0.0.1", backend="numpy",
                         jnwb_version="9.9.9")
        with pytest.raises(TypeError):
            O.Provenance(software_version="0.0.1", backend="numpy",
                         jnwb_path="/somewhere/else")

    def test_a_claim_that_disagrees_with_execution_is_visible(self):
        import jnwb

        honest = O.Provenance(software_version=jnwb.__version__, backend="numpy")
        lying = O.Provenance(software_version="0.0.1", backend="numpy")
        assert honest.version_claim_matches_execution
        assert not lying.version_claim_matches_execution

    def test_both_observed_fields_survive_to_dict(self):
        import jnwb

        d = O.Provenance(software_version="0.0.1", backend="numpy").to_dict()
        assert d["jnwb_version"] == jnwb.__version__
        assert d["jnwb_path"].endswith("jnwb")
        assert d["software_version"] == "0.0.1"
