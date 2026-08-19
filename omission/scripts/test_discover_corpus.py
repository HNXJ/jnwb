"""Tests for discover_corpus.py.

Every fixture is synthetic. No test depends on the real corpus, the real drive layout,
or today's session count -- if a test needed those, it would be re-freezing the topology
the script exists to discover.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover_corpus as dc  # noqa: E402


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """A synthetic, self-consistent corpus: 3 sessions, 2 subjects, TFR for two."""
    nwb = tmp_path / "nwb"
    tfr = tmp_path / "tfr"
    meta = tmp_path / "meta"
    repo = tmp_path / "repo"
    for d in (nwb, tfr, meta, repo / "artifacts" / "data"):
        d.mkdir(parents=True)

    stems = ["sub-AAA_ses-100_rec", "sub-AAA_ses-1000_rec", "sub-BBB_ses-200_rec"]
    for stem in stems:
        (nwb / f"{stem}.nwb").write_bytes(b"x" * 16)
        (meta / stem).mkdir()
        (meta / stem / "electrodes.csv").write_text("a\n")

    # TFR products for two of three sessions; the ses-1000 name is a prefix trap for ses-100.
    (tfr / "sub-AAA_ses-100_rec-probeA-V1-omission.npy").write_bytes(b"y")
    (tfr / "sub-AAA_ses-1000_rec-probeA-V1-omission.npz").write_bytes(b"y")
    (tfr / "sub-AAA_ses-1000_rec-probeB-V4-omission.npz").write_bytes(b"y")

    monkeypatch.setenv("OMISSION_NWB_DIR", str(nwb))
    monkeypatch.setenv("OMISSION_TFR_DIR", str(tfr))
    monkeypatch.setenv("OMISSION_META_DIR", str(meta))
    return {"repo": repo, "nwb": nwb, "tfr": tfr, "meta": meta, "stems": stems}


def _write_readiness(repo: Path, rows: list[dict]) -> None:
    path = repo / "artifacts" / "data" / "session_readiness.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stem", "tfr_ok"])
        writer.writeheader()
        writer.writerows(rows)


def _write_catalog(repo: Path, n_files: int, nwb_dir: Path) -> None:
    (repo / "artifacts" / "data" / "nwb_catalog.json").write_text(
        json.dumps({"n_files": n_files, "nwb_dir": str(nwb_dir)}), encoding="utf-8"
    )


# ---------------------------------------------------------------- discovery basics


def test_discovers_sessions_and_subjects_without_hardcoding(corpus):
    m = dc.build_manifest(corpus["repo"])
    assert m["totals"]["n_sessions"] == 3
    assert m["totals"]["subjects"] == ["AAA", "BBB"]
    assert m["roots"]["nwb_dir"]["resolved_from"] == "env:OMISSION_NWB_DIR"


def test_longest_stem_wins_so_prefixes_do_not_alias(corpus):
    """ses-100 must not absorb ses-1000's files."""
    m = dc.build_manifest(corpus["repo"])
    by_stem = {s["stem"]: s for s in m["sessions"]}
    assert by_stem["sub-AAA_ses-100_rec"]["tfr_n_files"] == 1
    assert by_stem["sub-AAA_ses-1000_rec"]["tfr_n_files"] == 2
    assert by_stem["sub-BBB_ses-200_rec"]["tfr_n_files"] == 0


def test_reports_formats_and_sidecars(corpus):
    m = dc.build_manifest(corpus["repo"])
    by_stem = {s["stem"]: s for s in m["sessions"]}
    assert by_stem["sub-AAA_ses-1000_rec"]["tfr_formats"] == ["npz"]
    assert all(s["sidecar_ok"] for s in m["sessions"])


def test_output_is_deterministic(corpus):
    a = dc.build_manifest(corpus["repo"])
    b = dc.build_manifest(corpus["repo"])
    a.pop("generated_utc"), b.pop("generated_utc")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ------------------------------------------------------------------- missing roots


def test_missing_root_is_a_mismatch_not_an_exception(corpus, monkeypatch):
    monkeypatch.setenv("OMISSION_NWB_DIR", str(corpus["repo"] / "does-not-exist"))
    m = dc.build_manifest(corpus["repo"])
    kinds = {x["kind"] for x in m["mismatches"]}
    assert "root_missing" in kinds
    assert m["blocking"] is True
    assert m["totals"]["n_sessions"] == 0


def test_unresolvable_root_reported(corpus, monkeypatch):
    monkeypatch.delenv("OMISSION_TFR_DIR", raising=False)
    monkeypatch.setattr(dc, "_resolve_roots", dc._resolve_roots)
    m = dc.build_manifest(corpus["repo"])
    tfr = m["roots"]["tfr_dir"]
    assert tfr["resolved_from"] in {"unresolved", "jnwb.paths.tfr_dir()"}


# -------------------------------------------------------------- readiness crosscheck


def test_readiness_gate_unsatisfiable_is_blocking(corpus):
    """The 2026-08-12 case: table says zero ready, disk says arrays exist."""
    _write_readiness(corpus["repo"], [{"stem": s, "tfr_ok": "False"} for s in corpus["stems"]])
    m = dc.build_manifest(corpus["repo"])
    hits = [x for x in m["mismatches"] if x["kind"] == "readiness_gate_unsatisfiable"]
    assert len(hits) == 1
    assert hits[0]["severity"] == dc.SEVERITY_BLOCKING
    assert m["blocking"] is True


def test_readiness_agreement_is_clean(corpus):
    _write_readiness(
        corpus["repo"],
        [
            {"stem": "sub-AAA_ses-100_rec", "tfr_ok": "True"},
            {"stem": "sub-AAA_ses-1000_rec", "tfr_ok": "True"},
            {"stem": "sub-BBB_ses-200_rec", "tfr_ok": "False"},
        ],
    )
    _write_catalog(corpus["repo"], 3, corpus["nwb"])
    m = dc.build_manifest(corpus["repo"])
    assert m["blocking"] is False, m["mismatches"]


def test_session_on_disk_missing_from_readiness_is_blocking(corpus):
    _write_readiness(corpus["repo"], [{"stem": "sub-AAA_ses-100_rec", "tfr_ok": "True"}])
    m = dc.build_manifest(corpus["repo"])
    kinds = {x["kind"] for x in m["mismatches"]}
    assert "session_absent_from_readiness" in kinds
    assert m["blocking"] is True


def test_catalog_count_disagreement_is_blocking(corpus):
    _write_readiness(
        corpus["repo"],
        [
            {"stem": "sub-AAA_ses-100_rec", "tfr_ok": "True"},
            {"stem": "sub-AAA_ses-1000_rec", "tfr_ok": "True"},
            {"stem": "sub-BBB_ses-200_rec", "tfr_ok": "False"},
        ],
    )
    _write_catalog(corpus["repo"], 21, corpus["nwb"])  # the classic stale count
    m = dc.build_manifest(corpus["repo"])
    hits = [x for x in m["mismatches"] if x["kind"] == "catalog_count_disagrees"]
    assert len(hits) == 1 and m["blocking"] is True


# ------------------------------------------------------------------- exit semantics


def test_exit_0_when_consistent(corpus, tmp_path):
    _write_readiness(
        corpus["repo"],
        [
            {"stem": "sub-AAA_ses-100_rec", "tfr_ok": "True"},
            {"stem": "sub-AAA_ses-1000_rec", "tfr_ok": "True"},
            {"stem": "sub-BBB_ses-200_rec", "tfr_ok": "False"},
        ],
    )
    _write_catalog(corpus["repo"], 3, corpus["nwb"])
    code = dc.main([
        "--repo-root", str(corpus["repo"]),
        "--out", str(tmp_path / "m.json"), "--check", "--quiet",
    ])
    assert code == 0


def test_exit_1_on_blocking_mismatch(corpus, tmp_path):
    _write_readiness(corpus["repo"], [{"stem": s, "tfr_ok": "False"} for s in corpus["stems"]])
    code = dc.main([
        "--repo-root", str(corpus["repo"]),
        "--out", str(tmp_path / "m.json"), "--check", "--quiet",
    ])
    assert code == 1


def test_exit_2_on_discovery_failure(corpus, tmp_path, monkeypatch):
    monkeypatch.setenv("OMISSION_NWB_DIR", str(tmp_path / "gone"))
    code = dc.main([
        "--repo-root", str(corpus["repo"]),
        "--out", str(tmp_path / "m.json"), "--check", "--quiet",
    ])
    assert code == 2


def test_manifest_contains_no_frozen_topology(corpus, tmp_path):
    """Guard against re-encoding today's observations as constants."""
    source = (Path(dc.__file__)).read_text(encoding="utf-8")
    for frozen in ["D:\\\\nwb", "D:/nwb", "D:\\\\analysis", "D:/analysis",
                   "C31o", "V182o", "V198o", "970", "1236", "1,236"]:
        assert frozen not in source, f"discover_corpus.py hardcodes {frozen!r}"
