"""Run one mutant, or the M0 control, of the t2 acceptance suite in one clone.

Usage: python run_mutant.py <clone dir> <M0 | M1 .. M9>

Applies <mode>.diff with git apply (M0 applies nothing), runs scripts/harness_gate.py and pytest on
the 30 files frozen in accept_t2.sh (no -x), restores the clone, asserts it is clean, then appends
one JSON line to results.jsonl. Full output goes to logs/<mode>_gate.log and logs/<mode>_pytest.log.
Standard library only.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

OUT = pathlib.Path("D:/repos/_work/exp_mut_t2")
RESULTS = OUT / "results.jsonl"
LOGS = OUT / "logs"
BASE = "ac995ddee147c4d6aa78ba15ecda7a998cd70a00"
MODES = ["M0"] + [f"M{k}" for k in range(1, 10)]
TESTS = [
    "tests/test_build_dashboard.py",
    "tests/test_changelog_fragments.py",
    "tests/test_ci_conclusion_gate.py",
    "tests/test_claim_vocabulary_prose.py",
    "tests/test_dashboard_page.py",
    "tests/test_dashboard_workflow.py",
    "tests/test_dependency_floors_are_installable.py",
    "tests/test_distribution_manifest_inspection.py",
    "tests/test_docs_user_navigation.py",
    "tests/test_fact_gate.py",
    "tests/test_fact_graph_boundary_units.py",
    "tests/test_harness_adversarial_gates.py",
    "tests/test_import_profile_receipt.py",
    "tests/test_learning_gate.py",
    "tests/test_module_docstrings_match_their_code.py",
    "tests/test_mutation_harness_validity.py",
    "tests/test_reference_claims_ledger.py",
    "tests/test_references_resolve.py",
    "tests/test_release_body_gate.py",
    "tests/test_release_body_script.py",
    "tests/test_release_contains_main.py",
    "tests/test_release_figure_registry.py",
    "tests/test_release_gate_receipt_history.py",
    "tests/test_release_recovery_gates.py",
    "tests/test_release_requires_an_empty_open_stack.py",
    "tests/test_release_version_is_unpublished.py",
    "tests/test_rng_parameters_by_use.py",
    "tests/test_signal_class.py",
    "tests/test_stack_metadata_contradictions.py",
    "tests/test_workflow_release_policy.py",
]
SUMMARY_RESULT = re.compile(r"^(FAILED|ERROR)\s+(\S+?\.py)\b")
SUMMARY_ANY = re.compile(r"^(FAILED|ERROR)\s")
COLLECT_ERROR = re.compile(r"ERROR collecting (\S+?\.py)\b")


def fail(msg):
    print(f"ABORT: {msg}", file=sys.stderr)
    sys.exit(2)


def git(clone, *args):
    return subprocess.run(["git", "-C", str(clone), *args], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8", errors="replace")


def status(clone):
    r = git(clone, "status", "--porcelain")
    if r.returncode != 0:
        fail(f"git status failed in {clone}: {r.stderr.strip()}")
    return r.stdout


def run(args, clone, env):
    return subprocess.run(args, cwd=str(clone), env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace")


def last_line(text):
    lines = text.splitlines()
    return lines[-1] if lines else ""


def summary_entries(text):
    """Lines of pytest's short test summary (after its header) that start FAILED or ERROR."""
    entries, in_summary = [], False
    for line in text.splitlines():
        if "short test summary info" in line:
            in_summary = True
            continue
        if in_summary and SUMMARY_ANY.match(line):
            entries.append(line)
    return entries


def failing_files(text):
    files = set()
    for line in summary_entries(text):
        m = SUMMARY_RESULT.match(line)
        if m:
            files.add(m.group(2))
    for line in text.splitlines():
        m = COLLECT_ERROR.search(line)
        if m:
            files.add(m.group(1))
    return sorted(files)


def main():
    if len(sys.argv) != 3:
        fail("usage: run_mutant.py <clone dir> <M0 | M1..M9>")
    clone = pathlib.Path(sys.argv[1])
    mode = sys.argv[2]
    if mode not in MODES:
        fail(f"unknown mode {mode}")
    if not (clone / "scripts" / "harness_gate.py").is_file():
        fail(f"not a jnwb tree: {clone}")
    if len(TESTS) != 30:
        fail(f"test list has {len(TESTS)} entries, expected 30")
    missing = [t for t in TESTS if not (clone / t).is_file()]
    if missing:
        fail(f"missing test files in {clone}: {missing}")
    head = git(clone, "rev-parse", "HEAD").stdout.strip()
    if head != BASE:
        fail(f"HEAD {head} is not the baseline {BASE}")
    if status(clone).strip():
        fail(f"clone not clean before the run: {clone}")
    LOGS.mkdir(parents=True, exist_ok=True)
    diff = OUT / f"{mode}.diff"
    applied = mode != "M0"
    t0 = time.monotonic()
    gate = pyt = None
    try:
        if applied:
            if not diff.is_file():
                fail(f"missing {diff}")
            ap = git(clone, "apply", str(diff))
            if ap.returncode != 0:
                fail(f"git apply {diff} failed: {ap.stderr.strip()}")
            changed = [ln for ln in status(clone).splitlines() if ln.strip()]
            if len(changed) != 1:
                fail(f"{mode} changed {changed}, expected exactly one file")
            print(f"applied {mode}: {changed[0]}", flush=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        gate = run([sys.executable, "scripts/harness_gate.py"], clone, env)
        print(f"gate rc={gate.returncode} last: {last_line(gate.stdout)}", flush=True)
        basetemp = f"D:/pytest_temp/exp_mut_{clone.name}"
        pyt = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   f"--basetemp={basetemp}", "-rfE", "--continue-on-collection-errors", *TESTS],
                  clone, env)
        print(f"pytest rc={pyt.returncode} last: {last_line(pyt.stdout)}", flush=True)
    finally:
        (LOGS / f"{mode}_gate.log").write_text(gate.stdout if gate else "", encoding="utf-8", newline="\n")
        (LOGS / f"{mode}_pytest.log").write_text(pyt.stdout if pyt else "", encoding="utf-8", newline="\n")
        git(clone, "checkout", "--", ".")
        git(clone, "clean", "-fdxq")
    left = status(clone).strip()
    if left:
        fail(f"clone not clean after restore: {left}")
    entries = summary_entries(pyt.stdout)
    record = {
        "mutant": mode,
        "gate_rc": gate.returncode,
        "gate_last": last_line(gate.stdout),
        "pytest_rc": pyt.returncode,
        "pytest_last": last_line(pyt.stdout),
        "failing_files": failing_files(pyt.stdout),
        "n_failed": len(entries),
        "seconds": round(time.monotonic() - t0, 1),
    }
    with open(RESULTS, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record) + "\n")
    print("RECORD " + json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
