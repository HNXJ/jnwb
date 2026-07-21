---
name: progress-review-plan
description: |
  Durable file-based backlog loop (PRP v3): Plan -> Progress -> Review -> Adapt -> Seal, plus Inspect.
---

# progress-review-plan (PRP v3)


Durably track backlog task state across sessions. State lives in JSON files under `artifacts/developer/`, not in chat memory.

## State Files & JSON Schema (v3)

All state is preserved in four files under `artifacts/developer/`:
- `plans.json` — Untriaged work, ideas, brainstorm entries, and checkpoints (written by Seal).
- `progress.json` — Live backlog of open and in-progress tracked work.
- `review.json` — Actioned-but-not-yet-verified work queue (trends toward empty).
- `adapt.json` — proposed tweaks to the agent skills, rules, or memory systems.

### Schema Fields Reference

#### 1. `plans.json`
* **`schema_version`** (int): 3
* **`description`** (str): Baseline roadmap description.
* **`brainstorm`** (array of objects):
  * `idea` (str): Feature or check idea.
  * `status` (str): `triaged` | `brainstorm`
* **`checkpoints`** (array of objects):
  * `timestamp` (str): ISO-8601 timestamp.
  * `tag` (str): Checkpoint label.
  * `status` (str): `verified` | `completed`
  * `evidence` (str): Text verifying successful loop outputs.
* **`items`** (array of objects):
  * `title` (str): Goal name.
  * `description` (str): Detailed requirements.
  * `priority` (str): `high` | `medium` | `low`
  * `status` (str): `planned` | `in-progress` | `completed`
  * `progress_targets` (array of str): Paths to files tracked in `progress.json`.

#### 2. `progress.json`
* **`schema_version`** (int): 3
* **`description`** (str): Backlog status note.
* **`last_updated`** (str): YYYY-MM-DD
* **`entries`** (array of objects):
  * `filename` (str): Base file name.
  * `path` (str): Workspace relative path (primary key).
  * `purpose` (str): Task description.
  * `score` (int): 0-100 rating (100 = done and verified).
  * `status` (str): `in-progress` | `done`
  * `last_verified` (str): YYYY-MM-DD
  * `evidence` (str): Command run + output verification receipt.

#### 3. `review.json`
* **`schema_version`** (int): 3
* **`description`** (str): Review pass receipt summaries.
* **`entries`** (array of objects):
  * `filename` (str): Base name.
  * `path` (str): Workspace relative path.
  * `score` (int/str): `unreviewed` | 0-100.
  * `verdict` (str): `NOT REVIEWED` | `ACCEPTED` | `ACCEPTED WITH CAVEATS` | `NOT ACCEPTED`
  * `issues` (str): Found bugs or gaps.
  * `review_command` (str): Command to run for validation.
  * `evidence` (str): Command execution output receipt.

#### 4. `adapt.json`
* **`schema_version`** (int): 3
* **`proposed_tweaks`** (array of objects):
  * `target` (str): Path of rules/skills file to update (e.g. `.agents/AGENTS.md`).
  * `change` (str): Plain text describing the rule modification.
  * `status` (str): `proposed` | `applied`
  * `evidence` (str): Commit or file-edit receipt verifying the rule.
  * `use_count` (int): Frequency count of how many times the rule has been referenced or successfully applied.
  * `rating` (float): Quality score (0.0 to 10.0) upvoted/downvoted based on the rule's effectiveness in preventing regression.

---

## Phased Actions & Automated Verification Script

Coordination is handled via the automated supervisor: `scripts/self_supervised_prp.py`.

### 1. Reconcile Registries (`--action sync`)
Reconciles paths between progress and review tables to prevent sync drift:
```bash
python scripts/self_supervised_prp.py --action sync
```

### 2. Self-Supervised Review Loop (`--action verify`)
Finds open entries in `review.json`, executes their `review_command` in a background subprocess, captures the stderr/stdout output, and automatically sets `score = 100` / `verdict = ACCEPTED` upon exit code 0 success, logging execution trace as `evidence`.
```bash
python scripts/self_supervised_prp.py --action verify
```

To force re-verification of already verified/ACCEPTED files (bypassing the stored skip condition when environment configurations or library functions change), append the `--force` flag:
```bash
python scripts/self_supervised_prp.py --action verify --force
```

### 3. Self-Evolving Adaptation Loop (`--action adapt`)
Scans verification error trace logs (e.g. for `NameError` or path issues) and automatically formats new proposed rules inside `adapt.json`. 

Every time a rule is dynamically updated or utilized in a task, increment the corresponding rule's `use_count` field in `adapt.json` and adjust its `rating` (upvote/downvote) to prune low-performing constraints over time.

### 4. Checkpoint State (`Seal`)
Saves a checkpoint of the current JSON database when `review.json` has been successfully cleared.

