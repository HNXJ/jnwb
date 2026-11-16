# Packet: structural adjudication of one code tree

You are an independent adjudicator. You judge one code tree against a written rubric. This packet is your only
authority. Do not spawn sub-agents.

Your directory: `{DIR}`. It holds `RUBRIC.md`, `baseline/` (a git clone of the repo `jnwb` at commit ac995dde,
unchanged) and `tree/` (a clone of the same commit with a changed `scripts/` directory). Read only inside
`{DIR}`. Do not read any other directory under `D:/repos/` or any scratch or temporary directory: other places
hold other trees, keys and results, and reading them voids the adjudication. Write only inside `{DIR}/notes/`
(create it). Do not edit, commit or push anything in `tree/` or `baseline/`.

What changed: `{DIR}/changes.diff` holds `git status --porcelain -- scripts` and `git diff HEAD -- scripts` of
`tree/` (new files are untracked and not in the diff: read them directly in `tree/`). With a shell you may run
those commands yourself; without one, read the file and the trees. You know nothing else about the tree: not who wrote it, not why, and no
automated result for it. It may satisfy the rubric or not.

Task: read `RUBRIC.md` in full first. It defines the question, the eight designated sites, the terms, the
scope, criteria L1 to L3, decided cases and the procedure. Follow the procedure. Whether the cells come out
right is not your question; how many implementations split cells, and who uses them, is. Where reading does
not settle where a site's cells are split and you have a shell, run the reader on a row: write a small script file in
`{DIR}/notes/`, run it by path with cwd = `{DIR}/tree`, `PYTHONDONTWRITEBYTECODE=1`, stdin closed
(`</dev/null`). Never `python -c`, `python -`, heredoc code or `sed -i`.

Rules: apply the criteria as written; the decided cases illustrate them and do not replace them. Do not guess
from names. If you cannot establish a criterion, the verdict is UNRESOLVED and you say what is missing. Do not
assume a prior probability of either verdict.

Report (at most 600 words), returned as your final message:
1. Every place under `tree/scripts/` that performs cell splitting, as `path:line`, each marked in scope or out
   of scope.
2. For each of the eight sites: the reader, and where its cells are split (`path:line`).
3. L1, L2, L3: met or not, one sentence of evidence each.
4. Commands run beyond reading. What you could not establish. Any place where the rubric did not decide the
   case as written. Your exact model id.
5. Last line, exactly one of: `VERDICT: PASS`, `VERDICT: FAIL`, `VERDICT: UNRESOLVED`.
