# Packet: structural adjudication of 23 code trees

You are an independent adjudicator. Judge each tree on its own against a written rubric. Do not spawn sub-agents. Do not edit, commit or push anything in the trees. Read ONLY: `D:/repos/_work/exp_t2adj/` (the rubric `RUBRIC.md`, the unchanged baseline `baseline/`, and the trees `k01` … `k23`). Do not read any other directory under `D:/repos/_work/` or any scratch directory other than your own: other places hold answer keys and earlier results, and reading them voids the adjudication. Your writable directory: `{OUT}` (create it; scripts, notes and the report go there).

Each `kNN` is a git clone of the baseline (repo `jnwb`, commit ac995dde) with a changed `scripts/` directory: `git -C <tree> status --porcelain` and `git -C <tree> diff HEAD` show what changed (new files are untracked: read them directly). The trees come from many sources and in shuffled order; some satisfy the rubric and some do not, in unknown proportion. You know nothing else about them and no automated result for them.

Task: read `RUBRIC.md` fully first; it defines the question, the eight sites, the terms, criteria S1 to S3, the anchors and the procedure. Then for every tree k01 to k23 follow the procedure and give `PASS`, `FAIL` or `UNRESOLVED`. Behaviour (whether cells come out right) is not your question; structure is. Where reading the code does not settle which delimiter logic is effective at a site, run the reader on a row: write a small script file in `{OUT}`, run it by path with cwd = the tree, `PYTHONDONTWRITEBYTECODE=1`, stdin closed (`</dev/null`). Never `python -c`, `python -`, heredoc code or `sed -i`.

Rules: judge each tree independently; do not balance verdicts; do not guess from names; if you cannot establish a criterion, say `UNRESOLVED` and what is missing.

Report: write `{OUT}/adjudication.md` and return the same text. First a table, one row per tree, exactly these columns:
`label | verdict | deciding criterion or anchor (S1/S2/S3/F1..F6/PASS anchor) | effective delimiter logic (path:line, one or several) | evidence in one sentence`
Then: commands you ran beyond reading; trees where you were least sure and why; exact model id. No summary of how many passed.
