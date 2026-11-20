"""Selftest for artifacts/process/ocma.schema.json."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
schema_path = ROOT / "artifacts" / "process" / "ocma.schema.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_schema_file_exists():
    assert schema_path.is_file()


def test_defs_hold_task_result_score(schema):
    assert {"task", "result", "score"} <= set(schema["$defs"])
    assert schema["oneOf"]


def test_good_task_and_score_validate(schema):
    jsonschema = pytest.importorskip("jsonschema")
    Validator = jsonschema.Draft202012Validator
    Validator.check_schema(schema)
    v = Validator(schema)
    good_task = {
        "kind": "task",
        "id": "t-demo",
        "objective": "demo",
        "reference": {"figure": "1"},
        "observable": {"name": "isi_cv", "unit": "1", "axis": "unit"},
        "signal_class": "spikes",
        "claim_class": "magnitude",
        "dataset": {"id": "000253"},
        "operations": ["isi_cv"],
        "estimand": "median isi_cv",
        "controls": ["shuffle"],
        "tolerance": "within 0.05 of receipt",
        "verdict_rule": "reproduces when within tolerance",
        "writes": ["artifacts/benchmarks/realdata/isi_cv_recompute_receipt.json"],
    }
    good_score = {
        "kind": "score",
        "task_id": "t-demo",
        "scorer": "agent-1",
        "criteria": {"Preregistration": 20, "Evidence": None},
        "total": 20,
        "feedback": "evidence criterion n/a",
        "evidence": ["artifacts/process/ocma_plan.md:42"],
    }
    v.validate(good_task)
    v.validate(good_score)


def test_incomplete_score_fails(schema):
    jsonschema = pytest.importorskip("jsonschema")
    v = jsonschema.Draft202012Validator(schema)
    with pytest.raises(jsonschema.ValidationError):
        v.validate({"kind": "score", "task_id": "t-demo"})
