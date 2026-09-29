"""Every example block in a skill executes, and says what kind of input it runs on.

An example that does not run teaches a call that fails; an example that runs on a random draw
reads, to an agent copying it, like a pattern for real data. So each block opens with one line,
``# Input: <class>.``, naming one of four input classes, and the class is checked against what the
block does:

| Class | The block |
|---|---|
| real NWB | reads a ``.nwb`` file the repository carries |
| deterministic array | builds its arrays without a random generator and reads no file |
| stochastic synthetic | draws its input from ``np.random.default_rng`` |
| calibration fixture | reads a ``.nwb`` file this test writes from ``jnwb.testing`` (``FIXTURES``) |

A skill may route only to public names, and ``jnwb.testing`` is not one, so a fixture example
names the file and this test writes it. The router's example is the pattern an agent meets first, so it runs on real NWB or a
deterministic array.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "skills"
ROUTER = "jnwb"

_BLOCK = re.compile(r"^```python\r?\n(.*?)^```", re.S | re.M)
_DECLARATION = re.compile(r"# Input: (?P<cls>[a-zA-Z ]+)\.")
CLASSES = ("real NWB", "deterministic array", "stochastic synthetic", "calibration fixture")
_NWB_PATH = re.compile(r"[\"']([^\"']+\.nwb)[\"']")
_RANDOM = re.compile(r"default_rng\(|np\.random\.|\brandom\.")
_FIXTURE = re.compile(r"\bjnwb\.testing\b")
BROWSER_EXPORT_CALLS = ("save_and_seal", "write_image", "to_image")


def _write_synth_session(path: Path) -> None:
    from jnwb.testing.nwb_fixtures import write_synth_nwb

    write_synth_nwb(path)


#: The calibration fixtures an example may read, by the file name it uses, and their writers.
FIXTURES = {"session.nwb": _write_synth_session}


def _blocks() -> list[tuple[str, int, str]]:
    out = []
    for md in sorted(SKILLS.glob("*/SKILL.md")):
        text = md.read_text(encoding="utf-8").replace("\r\n", "\n")
        for index, body in enumerate(_BLOCK.findall(text)):
            out.append((md.parent.name, index, body))
    return out


BLOCKS = _blocks()


def declared_class(block: str) -> str | None:
    """The input class the block's first line declares, or None."""
    first = block.splitlines()[0].strip() if block.strip() else ""
    match = _DECLARATION.fullmatch(first)
    return match["cls"] if match and match["cls"] in CLASSES else None


def declaration_mismatches(block: str) -> list[str]:
    """What the block does that its declared class does not allow, or why it declares none."""
    cls = declared_class(block)
    if cls is None:
        return [f"the first line is not '# Input: <class>.' with a class from {CLASSES}"]
    uses_random = bool(_RANDOM.search(block))
    uses_fixture = bool(_FIXTURE.search(block))
    nwb_paths = _NWB_PATH.findall(block)
    wrong = []
    if cls == "stochastic synthetic" and not uses_random:
        wrong.append("declares stochastic synthetic but draws nothing from a random generator")
    if cls != "stochastic synthetic" and uses_random:
        wrong.append(f"declares {cls} but draws from a random generator")
    if uses_fixture:
        wrong.append("imports jnwb.testing, which is not a public name a skill may route to")
    if cls == "calibration fixture":
        unknown = [p for p in nwb_paths if p not in FIXTURES]
        if not nwb_paths or unknown:
            wrong.append(f"declares calibration fixture but reads no file in FIXTURES: {unknown}")
    if cls == "deterministic array" and nwb_paths:
        wrong.append(f"declares deterministic array but reads {nwb_paths}")
    if cls == "real NWB":
        missing = [p for p in nwb_paths if not (REPO_ROOT / p).is_file()]
        if not nwb_paths or missing:
            wrong.append(f"declares real NWB but reads no file the repository carries: {missing}")
    return wrong


def _ids(blocks):
    return [f"{skill}#{index}" for skill, index, _ in blocks]


def test_every_skill_carries_an_example() -> None:
    skills = sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
    assert len(skills) >= 8, skills
    assert sorted({skill for skill, _, _ in BLOCKS}) == skills


@pytest.mark.parametrize("skill,index,block", BLOCKS, ids=_ids(BLOCKS))
def test_each_example_declares_the_input_class_it_uses(skill: str, index: int, block: str) -> None:
    assert declaration_mismatches(block) == [], skill


def test_the_router_example_runs_on_real_nwb_or_a_deterministic_array() -> None:
    classes = [declared_class(block) for skill, _, block in BLOCKS if skill == ROUTER]
    assert classes and all(c in CLASSES[:2] for c in classes), classes


@pytest.mark.parametrize("block,expected", [
    ("import numpy as np\nx = np.zeros(3)\n", "the first line is not"),
    ("# Input: made up.\nx = 1\n", "the first line is not"),
    ("# Input: deterministic array.\nrng = np.random.default_rng(0)\n", "draws from a random"),
    ("# Input: stochastic synthetic.\nx = np.zeros(3)\n", "draws nothing"),
    ("# Input: calibration fixture.\ninfo = jnwb.inspect('s.nwb')\n", "no file in FIXTURES"),
    ("# Input: calibration fixture.\nx = np.zeros(3)\n", "no file in FIXTURES"),
    ("# Input: deterministic array.\ninfo = jnwb.inspect('s.nwb')\n", "reads ['s.nwb']"),
    ("# Input: real NWB.\ninfo = jnwb.inspect('absent.nwb')\n", "reads no file"),
    ("# Input: stochastic synthetic.\nfrom jnwb.testing import synth\nrng = np.random.default_rng(0)\n",
     "not a public name"),
])
def test_a_wrong_declaration_is_caught(block: str, expected: str) -> None:
    assert any(expected in m for m in declaration_mismatches(block)), declaration_mismatches(block)


def _marks(block: str):
    if any(call in block for call in BROWSER_EXPORT_CALLS):
        return [pytest.mark.xdist_group("browser_export")]
    return []


RUNS = [pytest.param(block, marks=_marks(block), id=f"{skill}#{index}")
        for skill, index, block in BLOCKS]


@pytest.mark.parametrize("block", RUNS)
def test_each_example_executes_outside_the_checkout(block: str, tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """Run from a temporary directory, so a relative path cannot find the checkout by accident.

    A real NWB file the block names is copied there under the same relative path first, and a
    calibration fixture is written there under the name the block reads.
    """
    if "jnwb.vis" in block:
        pytest.importorskip("plotly")
        pytest.importorskip("kaleido")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if declared_class(block) == "real NWB":
        for rel in _NWB_PATH.findall(block):
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / rel, tmp_path / rel)
    if declared_class(block) == "calibration fixture":
        for name in _NWB_PATH.findall(block):
            FIXTURES[name](tmp_path / name)
    monkeypatch.chdir(tmp_path)
    code = compile(block, "skill example", "exec")
    try:
        if any(call in block for call in BROWSER_EXPORT_CALLS):
            from tests.test_vis import retry_browser_shutdown

            retry_browser_shutdown(lambda: exec(code, {"__name__": "__skill_example__"}))  # noqa: S102
        else:
            exec(code, {"__name__": "__skill_example__"})  # noqa: S102
    finally:
        plt.close("all")
