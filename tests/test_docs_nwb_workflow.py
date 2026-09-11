"""§5 harness: README, MkDocs nav, and skill alignment for the NWB workflow."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
MKDOCS = REPO_ROOT / "mkdocs.yml"
SKILL = REPO_ROOT / "skills" / "jnwb-nwb-data" / "SKILL.md"
TUTORIAL_DIR = REPO_ROOT / "examples" / "tutorials"


def test_readme_nwb_workflow_block_executes(tmp_path):
    from jnwb.testing.nwb_fixtures import (
        CODE_LABEL_A,
        TASK_TABLE,
        canonical_co_resident_options,
        write_synth_nwb,
    )

    path = tmp_path / "recording.nwb"
    receipt = write_synth_nwb(path, canonical_co_resident_options())

    info = jnwb.inspect(path)
    assert info["session"]["identifier"]
    assert any(t["name"] == TASK_TABLE for t in info["interval_tables"])

    et = jnwb.events(path, table=TASK_TABLE)
    assert et.time_unit == "seconds"
    assert et.n_events == len(receipt.task_onsets_s)

    onsets = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
    np.testing.assert_allclose(onsets, receipt.task_onsets_s[::2])

    spikes = jnwb.unit_spike_times(path, unit_index=0)
    assert spikes.size > 0
    _, fs_hz = jnwb.acquisition_channel(path, name="probe_0_lfp", channel=0)
    assert fs_hz == receipt.fs_hz


def test_readme_documents_inspect_events_onsets():
    text = README.read_text(encoding="utf-8")
    for symbol in ("inspect", "events", "event_onsets", "unit_spike_times"):
        assert f"jnwb.{symbol}" in text


def test_mkdocs_tutorials_nav_order():
    nav = yaml.safe_load(MKDOCS.read_text(encoding="utf-8"))["nav"]
    tutorials = next(item for item in nav if "Tutorials" in item)["Tutorials"]
    if isinstance(tutorials, dict):
        paths = list(tutorials.values())
    else:
        paths = [next(iter(entry.values())) for entry in tutorials]
    assert paths == [
        "tutorials/01_inspect_nwb.md",
        "tutorials/02_event_codes_and_onsets.md",
        "tutorials/03_align_spikes_lfp_to_events.md",
        "tutorials/04_compose_workflow.md",
    ]


def test_tutorial_docs_include_executable_sources():
    for n in ("01", "02", "03", "04"):
        md = (REPO_ROOT / "docs" / "tutorials" / f"{n}_*.md")
        matches = list(REPO_ROOT.glob(f"docs/tutorials/{n}_*.md"))
        assert len(matches) == 1
        text = matches[0].read_text(encoding="utf-8")
        script = TUTORIAL_DIR / f"{matches[0].stem}.py"
        assert script.exists()
        assert f'--8<-- "examples/tutorials/{script.name}"' in text


def test_skill_routes_to_public_nwb_api():
    text = SKILL.read_text(encoding="utf-8")
    for symbol in (
        "jnwb.inspect",
        "jnwb.events",
        "jnwb.event_onsets",
        "jnwb.unit_spike_times",
        "jnwb.acquisition_channel",
    ):
        assert symbol in text
    assert "paths.describe()" in text
    assert "not a substitute for `jnwb.inspect" in text
    assert "get_event_codes_and_timings" not in re.findall(
        r"^-\s+`get_event_codes", text
    )


@pytest.mark.parametrize(
    "path",
    sorted(TUTORIAL_DIR.glob("[0-9][0-9]_*.py")),
    ids=lambda p: p.name,
)
def test_tutorial_uses_public_jnwb_not_support_readers(path: Path):
    text = path.read_text(encoding="utf-8")
    assert "spike_times_for_unit" not in text
    assert "lfp_channel" not in text
    if path.name.startswith("03_") or path.name.startswith("04_"):
        assert "jnwb.unit_spike_times" in text


def test_mkdocs_strict_build():
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "docs_build.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
