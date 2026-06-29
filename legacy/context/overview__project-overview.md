---
status: canonical
scope: overview
source_of_truth: true
supersedes:
  - context/readme.md
  - context/vmemory.md
last_reviewed: 2026-04-06
---

# Project Overview: Omission Hierarchy

## Project Purpose
The **Omission** project is a large-scale neurophysiological investigation into the neural representations of predicted but absent stimuli (omissions). By recording from multiple areas across the visual and prefrontal cortical hierarchy, we aim to isolate "ghost signals" that reflect the brain's internal model, free from sensory input.

## High-Level Scientific Questions
1. How does the representation of an omitted stimulus evolve as it moves up the cortical hierarchy (V1 -> V4 -> TEO -> PFC)?
2. What are the laminar-specific signatures (superficial vs. deep) of predictive feedback during omissions?
3. Can we decode the identity of a missing stimulus from neural activity alone, and how does this decoding accuracy relate to behavioral performance and oculomotor "proxies" (pupil dilation, microsaccades)?

## Context Directory Map (`context/`)
- `overview/` — High-level project summaries, data availability, and area mappings.
- `specs/` — Canonical task definitions, pipeline standards, and reproducibility rules.
- `analysis/` — Roadmaps, decoding frameworks, and methodology-specific subdocs.

- `manuscript/` — Results summaries, poster content, and draft material.
- `operations/` — Troubleshooting notes and implementation history logs.
- `archive/` — Legacy material, prompts, and logs separated from the active source-of-truth.

## Major Analysis Tracks
1. **OMISSION-LFP (15-Step Pipeline)**: A standardized sequence from NWB validation to cluster-based permutation testing of directional causality (Granger).
2. **OMISSION-SPK (Population Dynamics)**: Unit-level analysis focusing on manifold trajectories, Fano Factor quenching, and identity decoding.
3. **OMISSION-BHV (Oculomotor Controls)**: Rigorous validation of neural signals against eye-tracking data (DVA, pupil) to account for microsaccade-induced artifacts.

## Repository & Context Conventions
- **Root Integrity**: No new folders or files in the root of any git directory without explicit confirmation.
- **Naming**: `codes/functions/` (underscores) for modules; `codes/scripts/` (hyphens) for entrypoints. No uppercase.
- **Versioning**: No version suffixes (`_v1`, `_v2`) in filenames.
- **Documentation**: All active non-code context is organized in `context/` with YAML frontmatter.
- **Scientific Integrity**: Prefer Gaussian smoothing for PSTHs and cluster-based permutations for spectral statistics to avoid phase-shifts and false positives.
