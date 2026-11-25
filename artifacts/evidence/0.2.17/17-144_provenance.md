# 17-144 provenance evidence (2026-11-25)

Question: do the three jaxfne-orchestrator isi_cv commits, `0e06993c`, `9980f58d` and `5fa63dd3` (16-12, todo
17-144), exist in any git store or bundle this machine can read?

Result: NOT FOUND in the readable locations listed here. Provenance is UNKNOWN for the parts that were not read,
and the commits are not verified absent. Blocker 17-144-src stays open.

Method (read-only, 2026-11-25): for each git directory, `git --git-dir=<dir> rev-parse --verify -q <prefix>^{commit}`
for each prefix; for each bundle, `git bundle list-heads` and `git bundle verify`; for the object scan, `git
cat-file --batch-all-objects --batch-check` on the repositories that passed `rev-parse`. Scans were run by a
read-only worker; its report is summarised here. Its report file was not written, so the counts below come from
that report and are not re-derived.

## 1. Sweep of the git stores on this machine

| Location | Readable | Checked | Result per prefix |
|---|---|---|---|
| `/mnt/c/Windows` (depth 40) | yes, no denied path | 0 git stores; 24 bundle-named files (21 not bundles; 3 directories) | not found |
| `/mnt/c/Users/*/AppData/Local/Temp` and `Packages` (depth 4) | yes | 391 `.git`: 340 valid, 51 invalid; 1 bundle (2 heads, no match) | not found |
| 166 directories named `jaxfne` under `/mnt` (depth 8); `/mnt/c/$Recycle.Bin` | yes | 140 rows: 131 `.git` (106 valid, 25 invalid); 9 bundles (5 usable, 4 stubs) | not found |
| System Volume Information on `/mnt/c`, `/mnt/d`, `/mnt/e`, `/mnt/f` | readable | 0 git stores or bundles | not found |
| `$Recycle.Bin` on `/mnt/d`, `/mnt/e`, `/mnt/f` | absent | none | none |
| `/mnt/h`, `/mnt/i`, `/mnt/k` (depth 7 to 12) | yes | 0 | not found |
| directories named `vlix`, `vwin-pc`, `cl-jnwb16e`, `cl-jnwb` under `/mnt` | none exists | none | none |

Earlier sweeps (before this record): this repository's clones, the `D:` clones and mirrors, every `.bundle` on `F:`,
`D:` and `E:`, the 13 repositories under `/mnt/c/Users`, and `main-vmac` (its checked scope).

## 2. Bundles fetched into a scratch bare repository

The scratch repository is outside every working tree. Each bundle was fetched with
`git fetch <bundle> "+refs/heads/*:refs/bundles/<n>/*"`, then the three prefixes were tested with `rev-parse`.

- 22 bundles fetched: none holds any of the three commits. The list covers `/mnt/f/repo_salvage_2026-11-10` (cl-reader-cursor,
  gate_6409, Gravia, jomission, jynx), `/mnt/d/cowork/jaxfne/scratch` (2), `/mnt/f/migrate/D/from_c_2026-11-11`,
  `/mnt/f/migrate/D/repos/_backup`, `/mnt/f/warehouse/jaxfne_clone_archive_2026-10-25` (7), `/mnt/f/warehouse/jaxfne_clone_rescue`
  (2), `/mnt/f/warehouse/jnwb_branch_archive`, `/mnt/c/Users/nejath` (Temp, Downloads, t40).
- `/mnt/f/repo_salvage_2026-11-10/jaxfne/jaxfne.bundle` (284,122,969 bytes; 109 heads) did not fetch. The error is
  `Could not read 4d049f8c0937a2fd9f75663ee686858fd4f6ee28` and `did not send all necessary objects`. `git bundle verify`
  reports a complete history. `4d049f8c` is not one of its heads, so the bundle's history references an object it does
  not contain.
- The `dev` head of that bundle (`22adb682`) fetches on its own. None of the three commits is in its history.
- The other 108 heads of `jaxfne.bundle` were not fetched one by one; they are unverified.

Not fetched: 12 bundles that the `find` listed: two `/mnt/f/migrate/D/cowork/jaxfne/scratch` copies (probably copies
of the `/mnt/d` bundles, not compared), four `/mnt/f/migrate/D/tmp/gate*.bundle`, two
`/mnt/f/migrate/D/tmp/claude/...` scratchpad bundles, a `jynx` backup copy under `/mnt/d/repos/_backup`, a Claude VM
bundle, and two `.lmstudio` bundles.

## 3. Residual unknowns

- `jaxfne.bundle`: 108 heads unverified because history object `4d049f8c` is missing from the bundle. This is the
  largest unknown, and it is damage, not absence.
- The 12 unfetched bundles above.
- The 21 Windows bundle-named binaries were tested only as bundles, not decoded. The 25 scoped and 51 Temp `.git`
  directories that are not repositories were checked by a loose-object name scan only.
- System Volume Information: existence only, not contents.
- `E:/cl-jnwb16e`, the orchestrator's clone, is absent from every `/mnt` drive. The orchestrator's own copies were not
  reachable from this machine.

## 4. What closes 17-144

Either jaxfne-orchestrator returns the three commits, or a check of the jaxfne repository (or a re-created bundle)
finds them. Until one of those, the item stays UNKNOWN and blocks 0.2.17.
