"""Controls for exp_scrub.py, exp_candidates.py and exp_table_check.py: each accepts a valid case, refuses each broken one.

Run: python -m pytest exp_scripts_test.py -q -p no:cacheprovider --basetemp=<a directory outside the repo>
"""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import exp_candidates  # noqa: E402
import exp_scrub  # noqa: E402
import exp_table_check  # noqa: E402

AGENT = "ade9393b0f61a8ab8"
EVAL = ('DEFECT | p | pre | a.py | "x = 1 | 2" | wrong-value | The constant is wrong.\n'
        'DEFECT | p | final | a.py | "x = 1 | 2" | wrong-value | The constant is wrong.\n'
        'DEFECT | q | final | b.py | "y" | scope | A file outside the scope changed.\n'
        "COUNT | 3\nGUESS | cannot tell\n")
CANDS = ('CAND | p-C01 | p | a.py | "x" | One.\nCAND | p-C02 | p | a.py | "y" | Two.\n'
         'CAND | q-C01 | q | b.py | "z" | Three.\n')
TABLE = ("ROW | p | 1 | yes | no | wrong-value | arm | p-C01, p-C02 | One defect.\n"
         "ROW | q | 1 | no | no | style | none | q-C01 | Not real.\nGUESS | p\n")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


def test_labels_are_fixed_by_the_seed_and_differ_between_arms():
    drawn = [exp_scrub.labels(n) for n in (1, 2, 3, 4)]
    assert drawn == [exp_scrub.labels(n) for n in (1, 2, 3, 4)]
    assert all(set(d.values()) == {"p", "q"} for d in drawn)


def test_reports_are_whole_scrubbed_and_keyed(tmp_path):
    ids = write(tmp_path / "ids.txt", AGENT + "\n")
    write(tmp_path / "A" / "1_worker.md", f"The worker {AGENT} changed exp_t1_A/x.py.\nLAST LINE A")
    write(tmp_path / "B" / "1_helper.md", "Helper table.\nLAST LINE H")
    write(tmp_path / "B" / "2_keeper.md", "The keeper took exp_t1_B1.\nLAST LINE K")
    exp_scrub.scrub_reports(1, tmp_path / "A", tmp_path / "B", ids, tmp_path / "out")
    text = (tmp_path / "out" / "reports_t1.txt").read_text(encoding="utf-8")
    assert all(s in text for s in ("LAST LINE A", "LAST LINE H", "LAST LINE K")), "no report is cut"
    assert AGENT not in text and "exp_t1_" not in text
    assert not exp_scrub.ROLE.search(text.replace("AGENT", ""))
    with open(tmp_path / "out" / "key_reports_t1.csv", newline="", encoding="utf-8") as fh:
        key = list(csv.DictReader(fh))
    assert sorted(r["role"] for r in key) == ["helper", "keeper", "worker"]
    lab = exp_scrub.labels(1)
    assert all(r["label"] == lab[r["arm"]] and r["report_id"].startswith(r["label"]) for r in key)


def test_diff_scrub_replaces_only_the_agent_token_and_logs_role_words(tmp_path):
    ids = write(tmp_path / "ids.txt", AGENT + "\n")
    diff = f"+++ b/x.py\n+tmp = 'D:/t/{AGENT}/f'\n+worker = 1\n-reviewer = 2\n+sha = '{AGENT}ff'\n"
    exp_scrub.scrub_diff(write(tmp_path / "in.diff", diff), ids, tmp_path / "out.diff", tmp_path / "log.txt")
    out = (tmp_path / "out.diff").read_text(encoding="utf-8")
    assert "+tmp = 'D:/t/AGENT/f'" in out and "+worker = 1" in out and f"{AGENT}ff" in out
    log = (tmp_path / "log.txt").read_text(encoding="utf-8")
    assert "agent ids replaced: 1" in log and "role word: 1" in log and "+worker = 1" in log


def pool(tmp_path, ev1=EVAL, ext='CLAIM | p-R01 | p | a.py | "x" | The value is wrong.\nNONE | q-R01\nCOUNT | 1\n'):
    key = write(tmp_path / "key.csv", "report_id,label,arm,role,file\np-R01,p,A,worker,f\nq-R01,q,B,keeper,g\n")
    exp_candidates.main(1, write(tmp_path / "e1.txt", ev1), "-", write(tmp_path / "x.txt", ext), key, tmp_path / "out")
    return tmp_path / "out"


def test_candidates_pool_without_source_and_merge_one_defect_on_two_snapshots(tmp_path):
    out = pool(tmp_path)
    lines = (out / "candidates_t1.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and sum(" | p | " in ln for ln in lines) == 2
    assert 'CAND | q-C01 | q | b.py | "y" | A file outside the scope changed.' in lines
    assert any('"x = 1 | 2"' in ln for ln in lines), "a pipe inside the quoted line survives"
    assert not any(w in "\n".join(lines) for w in ("eval", "report", "pre", "wrong-value", "R01"))
    with open(out / "key_candidates_t1.csv", newline="", encoding="utf-8") as fh:
        key = list(csv.DictReader(fh))
    assert sorted(r["source"] for r in key) == ["eval1", "eval1", "report"]
    assert {r["snapshots"] for r in key if r["source"] == "eval1"} == {"final+pre", "final"}


@pytest.mark.parametrize("ev1, ext, why", [
    (EVAL.replace("COUNT | 3", "COUNT | 2"), None, "COUNT"),
    (EVAL.replace("| scope |", "| nonsense |"), None, "class"),
    (EVAL.replace("GUESS | cannot tell\n", ""), None, "GUESS"),
    (EVAL, "NONE | p-R01\nCOUNT | 0\n", "without a CLAIM or NONE"),
    (EVAL, 'CLAIM | p-R01 | q | a.py | "x" | Wrong.\nNONE | q-R01\nCOUNT | 1\n', "not of attempt"),
])
def test_candidates_refuse_a_broken_input(tmp_path, ev1, ext, why):
    with pytest.raises(exp_candidates.Refused, match=why):
        pool(tmp_path, ev1, *([ext] if ext else []))
    assert not (tmp_path / "out").exists(), "nothing is written on refusal"


def check(tmp_path, table):
    return exp_table_check.check(write(tmp_path / "c.txt", CANDS), write(tmp_path / "t.txt", table))[0]


def test_table_check_accepts_a_valid_table(tmp_path):
    assert check(tmp_path, TABLE) == []
    run = subprocess.run([sys.executable, str(HERE / "exp_table_check.py"), str(tmp_path / "c.txt"), str(tmp_path / "t.txt")],
                         stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert run.returncode == 0 and run.stdout.startswith("TABLE OK: 2 rows hold 3 candidates")


@pytest.mark.parametrize("old, new, why", [
    ("p-C01, p-C02", "p-C01", "candidate p-C02 is in 0 rows"),
    ("| q-C01 |", "| q-C01, q-C01 |", "candidate q-C01 is in 2 rows"),
    ("p-C01, p-C02", "p-C01, p-C02, q-C01", "of the other attempt"),
    ("yes | no | wrong-value | arm", "no | yes | wrong-value | baseline-inside", "real only on the final snapshot"),
    ("no | no | style | none", "no | no | style | arm", "real on neither snapshot"),
    ("yes | no | wrong-value | arm", "yes | no | wrong-value | none", "real on a snapshot"),
    ("wrong-value", "bad-class", "class 'bad-class' unknown"),
    ("ROW | q | 1 | no | no | style | none | q-C01 | Not real.", "ROW | q | 1 | no | no | style | none |  | Not real.", "holds no candidate"),
    ("GUESS | p\n", "", "exactly one GUESS"),
    ("ROW | q | 1", "ROW | p | 1", "row number p/1 used 2 times"),
])
def test_table_check_refuses_each_broken_table(tmp_path, old, new, why):
    assert old in TABLE, "the perturbation must change the table"
    assert any(why in r for r in check(tmp_path, TABLE.replace(old, new)))
