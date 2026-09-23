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


def test_readme_nwb_workflow_block_executes(tmp_path, monkeypatch):
    """Execute the README's NWB block verbatim, which is what this test's name claims.

    It used to reimplement an analogous flow against the canonical fixture instead, so the
    README could have drifted to anything and this would still have passed.
    """
    from datetime import datetime, timezone

    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries

    # A file shaped like the README's example: a `trials` table whose code column is named
    # `stimulus`, which is the case the block exists to teach.
    nwb = NWBFile(
        session_description="readme example",
        identifier="README_BLOCK",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(
        name="shank0", description="d", location="unknown", device=device
    )
    for index in range(4):
        nwb.add_electrode(group=group, location="unknown", x=0.0, y=0.0, z=float(index))
    region = nwb.create_electrode_table_region(list(range(4)), "all")
    nwb.add_acquisition(
        ElectricalSeries(
            name="lfp", data=np.zeros((1000, 4), dtype="float32"),
            electrodes=region, starting_time=0.0, rate=1000.0,
        )
    )
    nwb.add_trial_column(name="stimulus", description="stimulus label")
    for index, onset in enumerate((0.1, 0.3, 0.5, 0.7)):
        nwb.add_trial(
            start_time=onset, stop_time=onset + 0.05,
            stimulus="grating" if index % 2 == 0 else "blank",
        )
    with NWBHDF5IO(str(tmp_path / "session.nwb"), "w") as io:
        io.write(nwb)

    fence = "```python" + chr(10) + "(.*?)```"
    blocks = re.findall(fence, README.read_text(encoding="utf-8"), re.S)
    workflow = [b for b in blocks if "jnwb.inspect(" in b and "event_onsets(" in b]
    assert len(workflow) == 1, f"expected one NWB workflow block, found {len(workflow)}"

    monkeypatch.chdir(tmp_path)
    namespace: dict = {}
    exec(compile(workflow[0], "README.md", "exec"), namespace)

    assert namespace["onsets"].size == 2
    np.testing.assert_allclose(namespace["onsets"], [0.1, 0.5])
    assert namespace["table"].code_column == "stimulus"


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
    # Derived from the scripts on disk rather than restated here: a hardcoded copy of this
    # list is a second registry that goes stale the moment a tutorial is added, which is
    # exactly what happened when 00 arrived.
    expected = [
        f"tutorials/{script.stem}.md"
        for script in sorted(TUTORIAL_DIR.glob("[0-9][0-9]_*.py"))
    ]
    assert len(expected) >= 8
    assert paths == expected


def test_tutorial_docs_include_executable_sources():
    for n in ("01", "02", "03", "04", "05", "06", "07", "08"):
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
    # Routing rows look like "- `jnwb.inspect(path_or_nwb)`". The MCP tools are named
    # further down in prose that steers readers to the public functions, which is correct,
    # so only a routing row counts as routing callers away from the public API.
    routed = re.findall(r"^-\s+`([A-Za-z_][\w.]*)", text, re.MULTILINE)
    assert routed, (
        "no routing rows matched, so this assertion checks nothing -- the skill's row "
        "format changed and the pattern above needs updating with it"
    )
    assert "get_event_codes_and_timings" not in routed, (
        "a routing row sends callers to an MCP tool instead of the public API"
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
    if path.name.startswith("03_") or path.name.startswith("08_"):
        assert "jnwb.unit_spike_times" in text


def test_mkdocs_strict_build():
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "docs_build.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
