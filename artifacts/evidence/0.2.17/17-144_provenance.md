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
| 166 directories named `jaxfne` under `/mnt` (depth 8); `/mnt/c/$Recycle.Bin` | yes | 140 rows: 131 `.git` (106 valid, 25 invalid; not reproduced, see section 5); 9 bundles (5 usable, 4 stubs) | not found |
| System Volume Information on `/mnt/c`, `/mnt/d`, `/mnt/e`, `/mnt/f` | existence only; contents not read | not read | not checked |
| `$RECYCLE.BIN` on `/mnt/d`, `/mnt/e`, `/mnt/f` | present: one SID directory each, holding only `desktop.ini` | no `.git` or bundle found | not found |
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
- The other 108 heads of `jaxfne.bundle` were not fetched one by one. Their objects were checked at pack level on 2026-11-25 (section 7): none of the three SHAs is in the pack.

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

## 5. Independent re-scan of the counts (4ef9c443 review, 2026-11-25)

The independent reviewer re-ran the counts and did not reproduce the worker's figures:

- Directories named `jaxfne` under `/mnt` at depth 8: 163 (section 1 says 166).
- `.git` in those directories: 32, of which 11 valid (section 1 says 131, of which 106 valid). Under `-path '*jaxfne*'` the same scan gives 27, of which 15 valid. A second review, in the ce738cd2 round, got 26, of which 14 valid, for that scope. The two reviews disagree, and the scope that yields 131 and 106 is still unresolved.

The scope that yields 131 and 106 is not stated in the worker's report, so those figures are not quoted as observed; they stand only as the worker's count. The result does not change: no valid store scanned holds `0e06993c`, `9980f58d` or `5fa63dd3`, and neither does `/mnt/e/repos/jnwb`.

The reviewer re-checked the rest of section 1: the `$RECYCLE.BIN` directories on `/mnt/d`, `/mnt/e` and `/mnt/f` (one SID directory each, `desktop.ini` only, no `.git` or bundle); System Volume Information (existence only, contents not read); Temp and Packages (391 `.git`, 340 valid, 51 invalid, 1 bundle); `/mnt/c/Windows` (0 `.git`, 24 bundle-named, 3 of them directories); the directories named `vlix`, `vwin-pc`, `cl-jnwb16e` and `cl-jnwb` under `/mnt`; and the 9 bundles in scope. It did not re-derive the 22 fetched bundles or `/mnt/h`, `/mnt/i`, `/mnt/k`.

## 6. GitHub check of the jnwb origin (2026-11-25)

Read-only: the public REST API and `git ls-remote`.

- `GET /repos/HNXJ/jnwb/commits/<prefix>` returns 422 for `0e06993c`, `9980f58d` and `5fa63dd3`. The same call returns 200 for `88a6eeec`, so short SHAs resolve (calibration).
- `git ls-remote origin` (94 refs) has no ref tip with any of the three prefixes.
- `HNXJ/jaxfne` ref tips (292 refs) have none either. Its commit lookup also returns 422 for the three prefixes, but that lookup is not calibrated. The three commits are jnwb commits on `E:/cl-jnwb16e`, so jaxfne is not their expected home.

Result: the three commits are not on the jnwb origin. 17-144 stays UNKNOWN. This does not show they are absent from the orchestrator's copy, which this machine cannot read.

## 7. Lead sweep and object-level checks (2026-11-25)

Reported by the jaxfne lead session (`main-jaxfne`); jnwb re-checked the bundle and the commit.

- `9b52c5e7` (`9b52c5e72adcf93940a570969ca46507a1f22d35`) is reached only by `refs/r4/heads/claude/site-overview-326890` in the scratch repositories `/mnt/d/tmp/_temp_clone_audit/isi_scratch.git` and `/mnt/f/migrate/D/tmp/_temp_clone_audit/isi_scratch.git`. No ref, reflog or stash in `/mnt/e/repos/jnwb/.git` or `/mnt/d/repos/jnwb/.git` reaches it. Bundle sha256 `aa88c08ace67a316db90808d1dbe3b2b87cdd722c765d000603a84dc5bc86148` (checked by jnwb on its scratch copy, not the original under `/mnt`); `git bundle verify` passes when run inside a repository. The tree has 724 paths, none named `isi_cv*` or under `realdata`, so `artifacts/benchmarks/realdata/isi_cv_recompute_receipt.json` is absent from the commit. The commit message cites a receipt outside the repository.
- `0e06993c`, `9980f58d`, `5fa63dd3`: not in that bundle. `git cat-file` finds none in 9187 readable stores or in the 42 alternate object directories that resolve on this machine. A closure check (`check_closure.sh`, 2026-11-25) follows alternates from the 42 resolvable targets to a fixed point. It reaches 40 object directories and finds none of the three SHAs in their own packs or loose objects; a known object is found, so the method works. Scope: `find` to depth 6 under `/mnt/c` through `/mnt/k` and `/home/hamm` (14921 entries; 5734 not readable as git; stderr discarded on the `/mnt/c` to `/mnt/k` scan).
- `jaxfne.bundle` at object level (jnwb, 2026-11-25): its pack holds 41,903 objects, and `git index-pack` verifies the pack checksum. None of the three SHAs is among them. Positive control: head `0b417733` is in the pack. Damage check: `4d049f8c` is absent, as section 2 says.
- Not covered, so not proof of absence: Stores whose alternates point at absent directories cannot be checked here. The lead reports 322 such stores (not re-derived here). Its tails file lists 17 absent targets, 16 distinct after `./` normalisation, among them `C:/workspace/jnwb` and the Mac `dev/jaxfne` and `dev/jomission` workspaces. An object held only in an absent directory cannot be ruled out; depth beyond 6; paths outside the scanned roots; `main-vmac` (offline).
- The receipt file is not in commit `9b52c5e7` or in any jnwb ref. No store was searched for the file by name.
- Result: the three commits stay UNKNOWN, not verified absent. 17-144 stays open, and 16-12 stays blocked.
