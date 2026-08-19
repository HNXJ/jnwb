# AGENT HANDOVER — Continue From Here
## Project: Omission Paradigm Multi-Area Laminar Neurophysiology
**Generated**: 2026-07-27 · **Repo**: `D:\workspace\omission` · **Branch/SHA**: `main` @ `7021dd7`

Call the user **Hamm**. Read Labyrinth first (`artifacts/.lab/`), leave a graph delta before you finish.

---

## 1. Where things stand (executive)

The manuscript has crossed from **active redesign** into **iterative scientific polishing**.

**Identity (frozen):**
> Visual omission recruits sparse higher-order spiking while broadly perturbing low-frequency cortical state.

**Headline dissociation (frozen numbers):**
| Quantity | Value | Standing |
|---|---|---|
| Inclusive O+ | **4.90%** (421/8,597), 95% CI [4.45%, 5.37%] | Headline — do not replace |
| LFP beta (14–30 Hz) | **77.51%** (6,771/8,736) | Headline |
| GLMM higher-order OR | **3.08×**, 95% CI [2.51, 3.78], z=10.726, p=7.25e-27 | Headline |
| Area-wise Spearman | **r = 0.93**, p=9.6e-05, n=10 | Fig5 / Results |
| Nested **O++** | **n = 39** (21 PFC / 18 FEF) | Nested robust subset only |

**5-figure lock:** Fig1 topology · Fig2 paradigm · Fig3 rasters · Fig4 spiking+GLMM · Fig5 spike–LFP dissociation. Connectivity stays Supplement.

---

## 2. Recent progress (what the last agent finished)

### Pass 9 — BioRxiv editorial polish (Option 3)
- Master DOCX typography densified (**0.75 in** margins), Methods after Discussion
- Westerberg-style captions (biological conclusion → panels → stats)
- Abstract thinned; Discussion rewritten (Westerberg hierarchy + Bastos predictive-routing extension)
- Figs 4–5 redesigned from receipted census (not fabricated per-area ORs)
- Backup: `context/omission-2026-manuscript-master.pre-polish-20260727.docx`

### Pass 10 — Freeze declared
- **FREEZE:** title, abstract structure, introduction, Figure 1, Figure 2, overall template/layout
- Graph node: `decision-freeze-frontmatter-polish-figs345`

### Pass 11 — Nested O++ + Figs 3–5 polish (latest)
- **O++** nested under inclusive O+ (does **not** replace 4.90%)
- Criteria (frozen receipt): R-family templates `RXRR/RRXR/RRRX`; area ∈ {FEF, PFC}; `mean_correlation ≥ 0.60`; `permutation_pval ≤ 0.05`
- Source table: `outputs/classification/grand_oplus_units.csv`
- Artifacts: `artifacts/data/oplusplus_census.json`, `outputs/classification/grand_oplusplus_units.csv`
- Classifier API: `jnwb.unit_classification` → `is_o_plusplus`, `assign_o_plusplus_from_template_table`, R-family metrics in `classify_unit`
- Results split into **four one-question subsections** (sparse? enriched? LFP broad? related?)
- Discussion paragraph: *What does omission add beyond predictable-vs-unpredictable for predictive routing?*
- Figs 3–5 restyled/re-embedded; notebook asserts all headline + O++ numbers
- `pytest tests/ -q` → **208 passed, 22 skipped**

---

## 3. Canonical paths

| Artifact | Path |
|---|---|
| Master DOCX | `context/omission-2026-manuscript-master.docx` (~8.5 MB) |
| Master PDF | `context/omission-2026-manuscript-master.pdf` (~1.3 MB, 13 pp) |
| Package zip | `omission_2026_manuscript_package.zip` (includes `artifacts/oplusplus_census.json`) |
| Labyrinth | `artifacts/.lab/labyrinth_unified.md` + `.json` |
| Census | `artifacts/data/empirical_response_census.json` |
| O++ receipt | `artifacts/data/oplusplus_census.json` |
| Repro notebook | `notebooks/reproducibility_master_pipeline.ipynb` (+ `.py`) |
| Fig generator | `scripts/polish_figures_4_5.py` |
| O++ census script | `scripts/build_oplusplus_census.py` |
| Manuscript O++ pass | `scripts/oplusplus_manuscript_pass.py` |
| BioRxiv polish | `scripts/biorxiv_polish_pass.py` (**restores from pre-polish backup** — do not run blindly) |

---

## 4. Vocabulary & stats discipline (non-negotiable)

**Use:** `support`, `indicate`, `quantify`, `co-occurs with`, `is consistent with`  
**Avoid:** `demonstrates`, `proves`, `causes`, `halts`

**Main-text stats only:**
1. Bootstrap 95% CIs  
2. One binomial logit GLMM (OR=3.08×)  
3. Cluster permutation + FDR for TFR  

**3-tool philosophy** — no new main-text dialects (Rayleigh, Granger nulls, etc.).

---

## 5. What to do next (highest ROI)

Do **not** restructure front matter. Continue iterative polish:

1. **Fig 3 quality** — real O++ exemplar rasters (not only labeled “O++ exemplar” on mean-matched grid); larger axis fonts; verify unit picks against `grand_oplusplus_units.csv`
2. **Fig 4 declutter** — keep GLMM inset dominant; O++ callout secondary; avoid crowding
3. **Fig 5 signature polish** — page-proof as the dissociation centerpiece
4. **Quantitative consistency sweep** — every of {4.90%, 77.51%, OR=3.08, r=0.93, O++=39} in figure / caption / Results / notebook (already mostly synced; re-check after any edit)
5. **Page-proof PDF** visually (Word reflow can still orphan captions)

**Do not:**
- Replace Abstract/Title 4.90% with O++ counts
- Expand beyond 5 main figures / add connectivity to main text
- Run `biorxiv_polish_pass.py` without reading it (it restores Pass-9 backup and can wipe Pass-11 edits)
- Commit/push unless Hamm asks

---

## 6. Verification commands

```bash
# O++ receipt
python scripts/build_oplusplus_census.py

# Headline number asserts
python notebooks/reproducibility_master_pipeline.py

# Tests
pytest tests/ -q

# Regenerate Figs 3–5 (then re-embed via oplusplus_manuscript_pass or physical replace)
python scripts/polish_figures_4_5.py

# PDF via Word COM
python -c "import win32com.client, pathlib; word=win32com.client.Dispatch('Word.Application'); doc=word.Documents.Open(r'D:/workspace/omission/context/omission-2026-manuscript-master.docx'); doc.SaveAs(r'D:/workspace/omission/context/omission-2026-manuscript-master.pdf', FileFormat=17); doc.Close(); word.Quit()"

# Package listing
python -c "import zipfile; z=zipfile.ZipFile(r'D:/workspace/omission/omission_2026_manuscript_package.zip'); print([f.filename for f in z.infolist()])"
```

---

## 7. Scientific note on O+ tiers

```
Inclusive O+ (4.90%, n=421)     ← manuscript headline / GLMM
        └── O++ (n=39, FEF/PFC) ← random-control robust nested subset
        └── weaker / latent O+  ← remainder of inclusive set
```

Classifier docstring target for shuffle SSO was O+ <1% (strict table has 7/6655); primary census 4.90% is the inclusive headline. Keep that distinction explicit in any new text.

---

## 8. Checklist for incoming agent

- [ ] Read this handout + skim Labyrinth Pass 9–11
- [ ] Confirm `pytest tests/ -q` still green
- [ ] Confirm `python notebooks/reproducibility_master_pipeline.py` passes
- [ ] Respect freeze list; touch Figs 3–5 / captions / consistency first
- [ ] Leave a Labyrinth delta (Pass 12+) before finishing

**Working tree:** dirty/`main` with many uncommitted changes — report status; do not commit unless Hamm requests.
