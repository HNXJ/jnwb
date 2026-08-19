# AGENT HANDOVER & ONBOARDING MANIFEST
## Project: Omission Paradigm Multi-Area Laminar Neurophysiology
**Generated**: 2026-07-27 | **Repository Path**: `D:\workspace\omission`

---

## 1. Executive Orientation & Mission Directive

Welcome to the **Omission Paradigm** computational neuroscience repository. Your primary responsibility is to preserve, maintain, and extend the highly calibrated, 5-figure canonical manuscript architecture for submission to top-tier systems neuroscience venues (*Neuron*, *Nature Neuroscience*, *Cell Reports*).

### The Single Core Biological Discovery
Every file, script, figure, and narrative section in this project orbits around **one fundamental empirical dissociation**:
$$\text{Representation}_{\text{omission}} = \Big\{ \text{sparse higher-order spiking } (4.90\%), \;\; \text{broad low-frequency field state } (77.51\%) \Big\}$$

- **Sparse Spiking**: Single-unit omission ramping (O+) occurs in **4.90% of neurons** ($421/8,597$ units, $95\%$ bootstrap CI: $[4.45\%, 5.37\%]$), concentrated in executive prefrontal (PFC: $9.32\%$) and frontal eye field (FEF: $9.40\%$) circuits vs visual cortex (V1: $1.11\%$).
- **Broad LFP Perturbation**: Local field potentials exhibit sustained, hierarchy-wide low-frequency beta power perturbations ($14\text{--}30$ Hz) across **$77.51\%$ of recorded channels** ($6,771/8,736$ channels, $95\%$ bootstrap CI: $[76.62\%, 78.38\%]$, permutation test $p < 0.01$, FDR-corrected).

---

## 2. Mandatory Canonical Vocabulary & Style Guide

You must strictly adopt the agent's established **computational deductive voice**. Never use narrative storytelling ("predictive coding says...") or uncalibrated causal verbs.

### Canonical Terminology (Use Verbatim)
- `"sparse higher-order spiking"`
- `"broad low-frequency LFP perturbation"`
- `"internally generated dynamics"`
- `"observed sensory state"`
- `"expected internal state"`
- `"perturbation of predictive state"`
- `"predictive routing"` (as an evaluated computational hypothesis, not a proven fact)

### Verbs to Enforce (Calibrated Observational Tone)
- **DO USE**: `support`, `indicate`, `quantify`, `co-occurs with`, `is consistent with`
- **DO NOT USE**: `demonstrates`, `proves`, `causes`, `halts`, `generates omission signals`

### Canonical Identity Sentence
This exact sentence must remain synchronized across Title, Abstract, Intro, Results, and Discussion:
> *"Visual omission recruits sparse higher-order spiking while broadly perturbing low-frequency cortical state."*

---

## 3. Standardized 3-Tool Statistical Philosophy

Do NOT introduce new statistical dialects (e.g. Rayleigh tests, ADF, Granger nulls, VAR orders) into the main text. Standardize all inferential claims onto **exactly 3 tools**:

1. **Bootstrap 95% Confidence Intervals**: 10,000-resample CIs for all population estimates, channel proportions, bar graphs, and figure error bounds.
2. **Hierarchical Mixed-Effects Model (GLMM)**: One Binomial Logit GLMM (`logit(P(is_o_plus)) ~ IsHigherOrder + (1|Subject) + (1|Session)`) for regional enrichment ($\text{OR} = 3.08x, 95\% \text{ CI: } [2.51, 3.78], z = 10.726, p = 7.25 \times 10^{-27}$, FDR-corrected).
   - **Explicit Inferential Unit Statement**: *"Population-level statistical inference treated recording sessions as the principal biological replication while accounting for nested observations arising from probes and neurons within sessions using generalized linear mixed-effects models."*
3. **Non-parametric Cluster Permutation Testing**: Spectral baseline-normalized TFR contrasts ($p < 0.01$, Benjamini-Hochberg FDR corrected).

---

## 4. The 5-Figure Canonical Narrative Architecture

The main text is strictly locked to **5 load-bearing figures**:

1. **Figure 1**: MaDeLaNe Dataset & 10-Area Recording Topology (*"What did you record?"*)
2. **Figure 2**: Omission Paradigm & 12-Condition Sequence Design (*"What was the experiment?"*)
3. **Figure 3**: Single-Unit Rasters (S+, S-, O+ Exemplars, selective task preference) (*"What does an omission neuron look like?"*)
4. **Figure 4**: Population Spiking Prevalence, Prefrontal Concentration & Logistic GLMM Forest Plot (*"How common are omission neurons, and where are they?"*)
5. **Figure 5**: Population LFP Beta Modulation & Parallel Spike-LFP Side-by-Side Dissociation Centerpiece (*"How does sparse spiking relate to broad field responses?"*)

*Note: All exploratory connectivity metrics (PLV, PAC, Granger Causality, Imaginary Coherence) live in the Supplement.*

---

## 5. Labyrinth Knowledge Graph System (`artifacts/.lab/`)

This project uses the **Labyrinth Adaptive Context Management Protocol (ACMP)** under `artifacts/.lab/`. Labyrinth is the shared memory and knowledge graph between agent and user.

- **Graph Engine**: [`artifacts/.lab/labyrinth_unified.json`](file:///D:/workspace/omission/artifacts/.lab/labyrinth_unified.json) (**276 Persisted Nodes**)
- **Compiled Markdown Graph**: [`artifacts/.lab/labyrinth_unified.md`](file:///D:/workspace/omission/artifacts/.lab/labyrinth_unified.md) (**38,882 Words**)
- **Labyrinth Reflex (Mandatory on Every Turn)**:
  1. *Read First*: Consult `.lab/` graph nodes before making claims.
  2. *Write Last*: Update graph state, append notes, or record status changes before completing a turn.
  3. *No Receipt, No Claim*: Standing is earned strictly through empirical receipts (`python` execution outputs, git SHAs, data hashes).

---

## 6. Primary Master Artifacts & Workspace Topology

Always work from and update these canonical master files in `D:\workspace\omission\`:

- **Master PDF**: [`context/omission-2026-manuscript-master.pdf`](file:///D:/workspace/omission/context/omission-2026-manuscript-master.pdf) (18 Pages, 1.84 MB)
- **Master DOCX**: [`context/omission-2026-manuscript-master.docx`](file:///D:/workspace/omission/context/omission-2026-manuscript-master.docx) (5.12 MB, Calibri Black)
- **Master Zip Package**: [`omission_2026_manuscript_package.zip`](file:///D:/workspace/omission/omission_2026_manuscript_package.zip) (7.62 MB, Clean 5-Figure Package)
- **Reproducibility Notebook**: [`notebooks/reproducibility_master_pipeline.ipynb`](file:///D:/workspace/omission/notebooks/reproducibility_master_pipeline.ipynb)
- **Author Response Statement**: [`docs/EPISCHEMIC_CALIBRATION_AUTHOR_RESPONSE.md`](file:///D:/workspace/omission/docs/EPISCHEMIC_CALIBRATION_AUTHOR_RESPONSE.md)

---

## 7. Mandatory Verification Commands Before Handing Off

Always run these commands to verify codebase and manuscript integrity before declaring completion:

```bash
# 1. Run full unit test suite
pytest tests/ -q

# 2. Re-render PDF from master DOCX via pywin32 Word COM
python -c "import win32com.client, pathlib; word = win32com.client.Dispatch('Word.Application'); doc = word.Documents.Open('D:/workspace/omission/context/omission-2026-manuscript-master.docx'); doc.SaveAs('D:/workspace/omission/context/omission-2026-manuscript-master.pdf', FileFormat=17); doc.Close(); word.Quit()"

# 3. Verify clean 5-figure package zip
python -c "import zipfile; z = zipfile.ZipFile('D:/workspace/omission/omission_2026_manuscript_package.zip'); print([f.filename for f in z.infolist()])"
```

---

### Handover Checklist for Incoming Agent
- [ ] Read `HANDOVER_ONBOARDING_MANIFEST.md` completely.
- [ ] Inspect [`artifacts/.lab/labyrinth_unified.md`](file:///D:/workspace/omission/artifacts/.lab/labyrinth_unified.md) to synchronize memory graph.
- [ ] Confirm `pytest tests/` passes with 206 clean passes.
- [ ] Enforce the 5-figure narrative and 3-tool statistical framework across all edits.
