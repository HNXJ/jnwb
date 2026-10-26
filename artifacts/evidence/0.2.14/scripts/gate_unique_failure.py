#!/usr/bin/env python3
"""Measure the unique failure of each gate in scripts/harness_gate.py.

For each gate N, one failure that gate N exists to catch is planted in the tree. Then
scripts/reconstruct_state.py and scripts/harness_gate.py run in that tree, and the gates
that printed a failure are read from the output. The planted bytes are restored after each
gate. A gate's failure is unique when no other gate fails.

Usage (the tree must hold scripts/harness_gate.py):

    python -u artifacts/evidence/0.2.14/scripts/gate_unique_failure.py <tree> \
        --receipt <file.json> [--md <file.md>] [--only N[,N...]]

The receipt and the markdown go outside the tree. The run stops when a restore does not
reproduce the pre-plant bytes, or when git status after a restore differs from git status
before the plant.

Method:
  1. Control: reconstruct, then harness, on the unplanted tree. All 22 gates must print PASS
     and the harness must exit 0.
  2. For each gate: apply the plant, run reconstruct and harness, read the output, restore.
     A plant with phase "after" is applied after reconstruct, because reconstruct rewrites
     artifacts/state.md and a plant in that file would be overwritten.
  3. A plant after which its own gate does not fail is a broken plant, reported as such.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

GATE_COUNT = 22
STEP_TIMEOUT_S = 900
PASS_PREFIX_CHARS = 60
HEAD_ZERO = b"0" * 40

#: FAIL header literals, copied from the _one(...) calls and adapter helpers in
#: scripts/harness_gate.py. A FAIL line that starts with one of these names its gate.
FAIL_HEADERS: Dict[int, Tuple[str, ...]] = {
    1: ("FAIL: jnwb/ frozen boundary check failed:",),
    2: ("FAIL: Skill tree uniqueness violated:",),
    3: ("FAIL: Hardcoded machine-local paths detected in tests:",),
    4: ("FAIL: Repository root allowlist violated:",),
    5: ("FAIL: Undocumented public symbols detected:",),
    6: ("FAIL: Dataset leakage detected in generic modules:",),
    7: ("FAIL: Version inconsistency detected:",),
    8: ("FAIL: Python support policy inconsistency detected:",),
    9: ("FAIL: Documented API does not match jnwb.__all__:",
        "FAIL: docs/api.md is out of sync with the API generator:"),
    10: ("FAIL: Documentation version does not match the package version:",),
    11: ("FAIL: Import-shadowing package detected at repository root:",),
    12: ("FAIL: Project identifiers found in jnwb/ code:",),
    13: ("FAIL: NWB onboarding surface misaligned:",),
    14: ("FAIL: Internal process vocabulary found in public documentation:",
         "FAIL: Item or problem identifiers found in jnwb/ or docs/:",
         "FAIL: CHANGELOG.md does not hold the entry template:"),
    15: ("FAIL: Coordination stack form is not machine-readable:",
         "FAIL: A process record disagrees with its own count or its citations:"),
    16: ("FAIL: Tracked files carry both line-ending conventions:",),
    17: ("FAIL: A stack field names something that does not exist:",),
    18: ("FAIL: A docs/api.md Type cell is not true of the runtime object:",),
    19: ("FAIL: A frozen-validated function no longer matches its verified body:",),
    20: ("FAIL: artifacts/state.md does not record the live HEAD:",
         "FAIL: artifacts/state.md does not carry its generated rows:"),
    21: ("FAIL: The computational contract is broken:",),
    22: ("FAIL: A typed fact is VIOLATED on the generated fact graph:",),
}

#: One plant per gate. Edit kinds:
#:   ("create", path, data)                    a new file, deleted on restore
#:   ("append", path, data)                    bytes added at the end, restored on exit
#:   ("sub", path, pattern, repl, expect)      bytes regex substitution; expect is the exact
#:                                             number of matches, or None for one or more
PLANTS: List[Dict[str, Any]] = [
    {"gate": 1, "phase": "before",
     "plant": "`jnwb/_u1_probe.py` created; its line is `import omission.jnwb_ext.trial_ontology as onto`",
     "source": "`tests/test_harness_adversarial_gates.py::TestHarnessAdversarialProbes::test_adversarial_probe_unauthorized_jnwb_import_rejected`",
     "edits": [("create", "jnwb/_u1_probe.py", b"import omission.jnwb_ext.trial_ontology as onto\n")]},
    {"gate": 2, "phase": "before",
     "plant": "`artifacts/u1_probe/SKILL.md` created; a SKILL.md outside `skills/`",
     "source": "`tests/test_gate2_ignores_nested_checkouts.py::test_a_plain_duplicate_tree_still_fails`",
     "edits": [("create", "artifacts/u1_probe/SKILL.md",
                b"---\nname: u1-probe\ndescription: probe\n---\n")]},
    {"gate": 3, "phase": "before",
     "plant": "`tests/_u1_probe.py` created; its line is `PATH = \"C:/workspace/data/session.nwb\"`",
     "source": "`tests/test_gates_reject_the_trees_they_passed.py::TestGate3SeesEveryDriveLetter::test_a_machine_local_path_on_any_drive_is_rejected`",
     "edits": [("create", "tests/_u1_probe.py", b'PATH = "C:/workspace/data/session.nwb"\n')]},
    {"gate": 4, "phase": "before",
     "plant": "`untracked_scratch.csv` created at the repository root",
     "source": "`tests/test_harness_adversarial_gates.py::TestHarnessAdversarialProbes::test_adversarial_probe_root_allowlist_violation_rejected`",
     "edits": [("create", "untracked_scratch.csv", b"a,b\n")]},
    {"gate": 5, "phase": "before",
     "plant": "`docs/errors.md`: every `UnitNotFoundError` renamed to `unit-not-found error` (the only hand-written page that names it)",
     "source": "`tests/test_errors_documented.py::TestTheGateWouldNoticeAMissingPage::test_one_missing_symbol_is_reported_by_name`",
     "edits": [("sub", "docs/errors.md", rb"\bUnitNotFoundError\b", b"unit-not-found error", None)]},
    {"gate": 6, "phase": "before",
     "plant": "`jnwb/_u1_probe.py` created; its line is `CONDITION = 'AXAB'`",
     "source": "`tests/test_harness_adversarial_gates.py::TestHarnessAdversarialProbes::test_adversarial_probe_dataset_leakage_rejected`",
     "edits": [("create", "jnwb/_u1_probe.py", b"CONDITION = 'AXAB'\n")]},
    {"gate": 7, "phase": "before",
     "plant": "`pyproject.toml`: `version = \"0.0.1\"` added under `[project]`, which differs from `jnwb.__version__`",
     "source": "`tests/test_harness_adversarial_gates.py::TestHarnessAdversarialProbes::test_adversarial_probe_version_inconsistency_rejected`",
     "edits": [("sub", "pyproject.toml", rb'(?m)^name = "jnwb"\n',
                b'name = "jnwb"\nversion = "0.0.1"\n', 1)]},
    {"gate": 8, "phase": "before",
     "plant": "`pyproject.toml`: `requires-python` changed from `>=3.12` to `>=3.12,<3.13` (an upper pin)",
     "source": "`tests/test_harness_adversarial_gates.py::TestHarnessAdversarialProbes::test_adversarial_probe_python_upper_pin_rejected`",
     "edits": [("sub", "pyproject.toml", re.escape(b'requires-python = ">=3.12"'),
                b'requires-python = ">=3.12,<3.13"', 1)]},
    {"gate": 9, "phase": "before",
     "plant": "`docs/api.md`: one prose line appended, so the generator's byte comparison fails",
     "source": "`tests/test_harness_adversarial_gates.py::TestDocumentationDriftGates::test_api_md_generator_drift_is_caught`",
     "edits": [("append", "docs/api.md", b"u1 probe line\n")]},
    {"gate": 10, "phase": "before",
     "plant": "`README.md`: `pip install jnwb==0.0.9` appended as prose",
     "source": "`tests/test_harness_adversarial_gates.py::TestDocumentationDriftGates::test_stale_install_pin_in_prose_is_caught`",
     "edits": [("append", "README.md", b"\npip install jnwb==0.0.9\n")]},
    {"gate": 11, "phase": "before",
     "plant": "`artifacts/_u1_probe.py` created; a .py file directly under the root directory `artifacts/`",
     "source": "`tests/test_gates_reject_the_trees_they_passed.py::TestGate11SeesNamespacePackages::test_a_directory_with_py_files_and_no_init_is_rejected`",
     "edits": [("create", "artifacts/_u1_probe.py", b"# probe\n")]},
    {"gate": 12, "phase": "before",
     "plant": "`jnwb/_u1_probe.py` created; its line is `NAME = \"omission\"`",
     "source": "`tests/test_harness_adversarial_gates.py::TestProjectIdentifierGate::test_catches_project_name_in_identifier`",
     "edits": [("create", "jnwb/_u1_probe.py", b'NAME = "omission"\n')]},
    {"gate": 13, "phase": "before",
     "plant": "`mkdocs.yml`: the nav line for `tutorials/01_nwb_basics.md` commented out",
     "source": "`tests/test_gates_reject_the_trees_they_passed.py::TestGate13ChecksBehaviourNotPresence::test_a_commented_out_nav_entry_is_rejected`",
     "edits": [("sub", "mkdocs.yml", re.escape(b"      - NWB Basics: tutorials/01_nwb_basics.md\n"),
                b"      # - NWB Basics: tutorials/01_nwb_basics.md\n", 1)]},
    {"gate": 14, "phase": "before",
     "plant": "`docs/glossary.md`: a line with the word `packet` appended",
     "source": "`tests/test_harness_adversarial_gates.py::TestGate14InternalProcessVocabulary::test_a_page_naming_a_delegation_packet_fails`",
     "edits": [("append", "docs/glossary.md", b"\nPacket probe.\n")]},
    {"gate": 15, "phase": "before",
     "plant": "`artifacts/open_stack.md`: a three-column table with a two-cell row appended",
     "source": "`tests/test_harness_adversarial_gates.py::TestGate15ProblemRowsKeepTheirTableShape::test_a_row_missing_a_cell_is_rejected`",
     "edits": [("append", "artifacts/open_stack.md",
                b"\n| Test | Finding | Found by |\n|---|---|---|\n| u1 | a defect |\n")]},
    {"gate": 16, "phase": "before",
     "plant": "`LICENSE`: a CRLF line appended to an LF file",
     "source": "`tests/test_harness_adversarial_gates.py::TestGate16LineEndingConsistency::test_a_mixed_file_is_rejected`",
     "edits": [("append", "LICENSE", b"\r\n")]},
    {"gate": 17, "phase": "before",
     "plant": "`artifacts/todo_stack.md`: `Blocked by: 15-20.` changed to `Blocked by: 99-99.`",
     "source": "`tests/test_harness_adversarial_gates.py::TestStackPointersResolve::test_a_block_on_a_retired_item_fails`",
     "edits": [("sub", "artifacts/todo_stack.md", re.escape(b"Blocked by: 15-20."),
                b"Blocked by: 99-99.", 1)]},
    {"gate": 18, "phase": "before",
     "plant": "`docs/api.md`: the Type cell of `jnwb.ChannelIndexError` changed from `class` to `function`",
     "source": "`tests/test_harness_adversarial_gates.py::TestApiMdMemberTypes::test_one_wrong_cell_is_enough`",
     "edits": [("sub", "docs/api.md", re.escape(b"| jnwb.ChannelIndexError | class |"),
                b"| jnwb.ChannelIndexError | function |", 1)]},
    {"gate": 19, "phase": "before",
     "plant": "`jnwb/_bins.py`: `+ 0.0` added to the `bins_within` body (a code change, same value)",
     "source": "`tests/test_frozen_validated.py::test_a_changed_body_fails`",
     "edits": [("sub", "jnwb/_bins.py",
                re.escape(b"    span, width = float(span), float(bin_width)\n"),
                b"    span, width = float(span), float(bin_width) + 0.0\n", 1)]},
    {"gate": 20, "phase": "after",
     "plant": "`artifacts/state.md`, regenerated first: its HEAD row set to 40 zeros",
     "source": "`tests/test_harness_adversarial_gates.py::TestGate20StateFileHead::test_a_zeroed_head_row_fails_naming_both_commits`",
     "edits": [("sub", "artifacts/state.md", rb"(?m)^\| HEAD \| `[0-9a-f]{40}` \|$",
                b"| HEAD | `" + HEAD_ZERO + b"` |", 1)]},
    {"gate": 21, "phase": "before",
     "plant": "`artifacts/evidence/0.2.6/computational_order.md`: the section 3 row for `classify_layer_from_depth` deleted",
     "source": "(designed)",
     "edits": [("sub", "artifacts/evidence/0.2.6/computational_order.md",
                rb"(?m)^" + re.escape(b"| `classify_layer_from_depth` | n_electrodes | 100000,")
                + rb"[^\r\n]*\r?\n", b"", 1)]},
    {"gate": 22, "phase": "before",
     "plant": "`jnwb/_bins.py`: a function appended whose body calls `np.random.seed(0)` (the fact graph reads tracked files only)",
     "source": "(designed)",
     "edits": [("append", "jnwb/_bins.py",
                b"\n\nimport numpy as np\n\n\ndef _u1_probe():\n    np.random.seed(0)\n")]},
]


class PlantError(Exception):
    """A plant whose anchor did not apply exactly as stated."""


def rel(tree: Path, path: Path) -> str:
    return path.relative_to(tree).as_posix()


def git_status(tree: Path) -> str:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=tree,
                          capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise SystemExit(f"STOP: git status failed in {tree}: {proc.stderr.decode(errors='replace')}")
    return proc.stdout.decode("utf-8", errors="replace")


def run_step(tree: Path, script: str) -> Tuple[int, str]:
    proc = subprocess.run([sys.executable, script], cwd=tree, capture_output=True,
                          timeout=STEP_TIMEOUT_S)
    text = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    return proc.returncode, text


def apply_edits(tree: Path, edits: List[Tuple[Any, ...]], ledger: Dict[str, Any],
                state_path: Path) -> List[str]:
    notes: List[str] = []
    for edit in edits:
        op, relpath = edit[0], edit[1]
        path = tree / relpath
        if op == "create":
            if path.exists():
                raise PlantError(f"{relpath} already exists")
            missing: List[Path] = []
            parent = path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                ledger["dirs"].append(directory)
            path.write_bytes(edit[2])
            ledger["created"].append(path)
            notes.append(f"created {relpath}")
        elif op == "append":
            original = path.read_bytes()
            if path != state_path:
                ledger["orig"].setdefault(path, original)
            path.write_bytes(original + edit[2])
            notes.append(f"appended {len(edit[2])} bytes to {relpath}")
        elif op == "sub":
            pattern, repl, expect = edit[2], edit[3], edit[4]
            original = path.read_bytes()
            if path != state_path:
                ledger["orig"].setdefault(path, original)
            updated, count = re.subn(pattern, repl, original)
            wanted = "one or more" if expect is None else str(expect)
            if (count < 1) if expect is None else (count != expect):
                raise PlantError(f"{relpath}: pattern matched {count} times, wanted {wanted}")
            path.write_bytes(updated)
            notes.append(f"{relpath}: {count} substitution(s)")
        else:
            raise PlantError(f"unknown edit kind {op!r}")
    return notes


def restore(tree: Path, ledger: Dict[str, Any], control_state: bytes,
            state_path: Path) -> List[str]:
    problems: List[str] = []
    for path, data in ledger["orig"].items():
        path.write_bytes(data)
    for path in ledger["created"]:
        if path.exists():
            path.unlink()
    for directory in reversed(ledger["dirs"]):
        if directory.exists():
            try:
                directory.rmdir()
            except OSError as exc:
                problems.append(f"could not remove {rel(tree, directory)}: {exc}")
    state_path.write_bytes(control_state)
    for path, data in ledger["orig"].items():
        if path.read_bytes() != data:
            problems.append(f"bytes differ after restore: {rel(tree, path)}")
    for path in ledger["created"]:
        if path.exists():
            problems.append(f"created file remains: {rel(tree, path)}")
    for directory in ledger["dirs"]:
        if directory.exists():
            problems.append(f"created directory remains: {rel(tree, directory)}")
    if state_path.read_bytes() != control_state:
        problems.append("state file differs from its control bytes after restore")
    return problems


def parse_harness(text: str, prefixes: Dict[int, str]) -> Tuple[Set[int], Set[int], List[str]]:
    """Gate numbers that failed and that passed, read from one harness run's output."""
    failed: Set[int] = set()
    passed: Set[int] = set()
    not_run: Set[int] = set()
    unmapped: List[str] = []
    overall: Optional[str] = None
    for line in text.splitlines():
        if line.startswith("FAIL: "):
            hits = [g for g, headers in FAIL_HEADERS.items()
                    if any(line.startswith(h) for h in headers)]
            if len(hits) == 1:
                failed.add(hits[0])
            else:
                unmapped.append(line)
        elif line.startswith("ERROR: gate "):
            match = re.match(r"ERROR: gate (\d+) raised ", line)
            if match:
                failed.add(int(match.group(1)))
            else:
                unmapped.append(line)
        elif line.startswith("PASS: "):
            hits = [g for g, prefix in prefixes.items() if line.startswith(prefix)]
            if len(hits) == 1:
                passed.add(hits[0])
            else:
                unmapped.append(line)
        elif line.startswith("NOT RUN: gate "):
            match = re.match(r"NOT RUN: gate (\d+) ", line)
            if match:
                not_run.add(int(match.group(1)))
            else:
                unmapped.append(line)
        elif line.startswith("OVERALL: "):
            overall = line
    problems: List[str] = []
    if unmapped:
        problems.append(f"{len(unmapped)} line(s) not mapped to a gate, first: {unmapped[0]!r}")
    if overall is not None:
        match = re.search(r"failed: (\[[0-9, ]*\]|none);", overall)
        if match is None:
            problems.append(f"OVERALL line has no failed list: {overall!r}")
        else:
            listed = (set() if match.group(1) == "none"
                      else {int(x) for x in re.findall(r"\d+", match.group(1))})
            if listed != failed:
                problems.append(f"OVERALL lists failed {sorted(listed)}, the FAIL lines give "
                                f"{sorted(failed)}")
    elif failed:
        problems.append("failures printed but no OVERALL line")
    if failed & passed:
        problems.append(f"gates both failed and passed: {sorted(failed & passed)}")
    if not_run:
        problems.append(f"gates not run: {sorted(not_run)}")
    missing = sorted(set(range(1, GATE_COUNT + 1)) - (failed | passed | not_run))
    if missing:
        problems.append(f"gates with no line in the output: {missing}")
    return failed, passed, problems


def prefixes_from_control(control_text: str) -> Dict[int, str]:
    """Gate k's PASS line is the k-th PASS line of an all-pass run, which prints in gate order."""
    lines = [line for line in control_text.splitlines() if line.startswith("PASS: ")]
    if len(lines) != GATE_COUNT:
        raise SystemExit(f"STOP: control run printed {len(lines)} PASS lines, wanted {GATE_COUNT}")
    prefixes = {k: lines[k - 1][:PASS_PREFIX_CHARS] for k in range(1, GATE_COUNT + 1)}
    if len(set(prefixes.values())) != GATE_COUNT:
        raise SystemExit("STOP: PASS prefixes are not unique; the line-to-gate map is unsound")
    return prefixes


def run_one(tree: Path, plant: Dict[str, Any], prefixes: Dict[int, str],
            control_state: bytes, state_path: Path) -> Dict[str, Any]:
    ledger: Dict[str, Any] = {"orig": {}, "created": [], "dirs": []}
    result: Dict[str, Any] = {
        "gate": plant["gate"], "phase": plant["phase"], "plant": plant["plant"],
        "source": plant["source"], "notes": [], "error": None, "problems": [],
        "failed": [], "passed": 0, "reconstruct_rc": None, "harness_rc": None,
        "restore_problems": [], "seconds": None,
    }
    started = time.monotonic()
    try:
        if plant["phase"] == "before":
            result["notes"] += apply_edits(tree, plant["edits"], ledger, state_path)
        rc_rec, _ = run_step(tree, "scripts/reconstruct_state.py")
        result["reconstruct_rc"] = rc_rec
        if plant["phase"] == "after":
            result["notes"] += apply_edits(tree, plant["edits"], ledger, state_path)
        rc_gate, text = run_step(tree, "scripts/harness_gate.py")
        result["harness_rc"] = rc_gate
        failed, passed, problems = parse_harness(text, prefixes)
        result["failed"] = sorted(failed)
        result["passed"] = len(passed)
        result["problems"] = problems
        expected_rc = 1 if failed else 0
        if rc_gate != expected_rc:
            result["problems"].append(f"harness exit {rc_gate}, wanted {expected_rc}")
    except PlantError as exc:
        result["error"] = f"plant error: {exc}"
    except subprocess.TimeoutExpired:
        result["error"] = f"timeout after {STEP_TIMEOUT_S} s"
    except OSError as exc:
        result["error"] = f"plant error: {type(exc).__name__}: {exc}"
    finally:
        result["restore_problems"] = restore(tree, ledger, control_state, state_path)
        result["seconds"] = round(time.monotonic() - started, 1)
    return result


def markdown_rows(results: List[Dict[str, Any]]) -> str:
    rows = ["| id | plant | gates that failed | unique | source of the plant |",
            "|---|---|---|---|---|"]
    for r in results:
        if r["status"] == "measured":
            failed = ", ".join(f"A{g}" for g in r["failed"])
            unique = "yes" if r["unique"] else "no"
        elif r["status"] == "broken plant":
            failed = f"not a result (own gate A{r['gate']} passed)"
            unique = "no (broken plant)"
        else:
            failed = f"not a result ({r['status']})"
            unique = "unknown"
        rows.append(f"| A{r['gate']} | {r['plant']} | {failed} | {unique} | {r['source']} |")
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("tree", help="repository tree to plant in; must hold scripts/harness_gate.py")
    parser.add_argument("--receipt", required=True, help="JSON receipt, written after each gate")
    parser.add_argument("--md", default="", help="markdown rows for section E, written at the end")
    parser.add_argument("--only", default="", help="comma-separated gate numbers to plant (smoke runs)")
    args = parser.parse_args()

    tree = Path(args.tree).resolve()
    if not (tree / "scripts" / "harness_gate.py").is_file():
        print(f"REFUSED: {tree} has no scripts/harness_gate.py")
        return 2
    receipt = Path(args.receipt).resolve()
    if tree in receipt.parents:
        print("REFUSED: the receipt must be outside the tree")
        return 2
    state_path = tree / "artifacts" / "state.md"

    selected = PLANTS
    if args.only:
        wanted = {int(x) for x in args.only.split(",")}
        selected = [p for p in PLANTS if p["gate"] in wanted]
        if len(selected) != len(wanted):
            print(f"REFUSED: --only names gates outside 1..{GATE_COUNT}")
            return 2

    for plant in selected:
        for edit in plant["edits"]:
            path = tree / edit[1]
            if edit[0] == "create" and path.exists():
                print(f"REFUSED: {edit[1]} exists before the plant; the tree is not clean")
                return 2
            if edit[0] != "create" and not path.is_file():
                print(f"REFUSED: plant for gate {plant['gate']} needs {edit[1]}, which is absent")
                return 2

    baseline = git_status(tree)
    print(f"baseline git status: {baseline!r}", flush=True)

    rc_rec, _ = run_step(tree, "scripts/reconstruct_state.py")
    if rc_rec != 0 or not state_path.is_file():
        print(f"STOP: control reconstruct exit {rc_rec}")
        return 2
    control_state = state_path.read_bytes()
    rc_ctl, control_text = run_step(tree, "scripts/harness_gate.py")
    summary = [line for line in control_text.splitlines() if line.strip()][-1:]
    print(f"control: harness exit {rc_ctl}; last line: {summary}", flush=True)
    not_passing = [line for line in control_text.splitlines()
                   if line.startswith(("FAIL: ", "ERROR: ", "NOT RUN: "))]
    if rc_ctl != 0 or not_passing or "ALL HARNESS GATES PASSED" not in control_text:
        print(f"STOP: control is not all PASS: exit {rc_ctl}, not passing lines {not_passing[:3]}")
        return 2
    prefixes = prefixes_from_control(control_text)
    control_failed, control_passed, control_problems = parse_harness(control_text, prefixes)
    if control_failed or len(control_passed) != GATE_COUNT or control_problems:
        print(f"STOP: control lines do not map to 22 gates: passed={len(control_passed)} "
              f"problems={control_problems}")
        return 2
    control_record = {"reconstruct_rc": rc_rec, "harness_rc": rc_ctl,
                      "pass_lines": len([x for x in control_text.splitlines()
                                         if x.startswith("PASS: ")]),
                      "summary": summary[0] if summary else ""}

    results: List[Dict[str, Any]] = []
    for plant in selected:
        before = git_status(tree)
        if before != baseline:
            print(f"STOP: git status before the gate {plant['gate']} plant differs from the baseline")
            return 3
        result = run_one(tree, plant, prefixes, control_state, state_path)
        if result["restore_problems"]:
            print(f"STOP: restore after gate {plant['gate']} failed: {result['restore_problems']}")
            return 3
        after = git_status(tree)
        if after != before:
            print(f"STOP: git status after gate {plant['gate']} restore differs from before the plant")
            return 3
        gate = plant["gate"]
        if result["error"] or result["problems"]:
            result["status"] = "error"
        elif gate not in result["failed"]:
            result["status"] = "broken plant"
        else:
            result["status"] = "measured"
        result["unique"] = (result["failed"] == [gate]) if result["status"] == "measured" else None
        results.append(result)
        print(f"A{gate} status={result['status']} failed={result['failed']} "
              f"unique={result['unique']} rc_gate={result['harness_rc']} "
              f"seconds={result['seconds']} notes={result['notes']} "
              f"error={result['error']} problems={result['problems']}", flush=True)
        receipt.write_text(json.dumps({"tree": str(tree), "control": control_record,
                                       "results": results}, indent=2) + "\n",
                           encoding="utf-8")

    if args.md:
        Path(args.md).write_text(markdown_rows(results), encoding="utf-8")
    print(f"DONE: {len(results)} gate(s) planted; receipt {receipt}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
