---
status: canonical
scope: overview
source_of_truth: true
supersedes:
  - context/docs/notes/data-availability-summary.md
last_reviewed: 2026-04-06
---

# Data Availability Summary

This document provides a comprehensive overview of the available data modalities across the 13 recorded sessions.

## Session Overview
| Session | Trials | Conditions | Units (SPK) | LFP | Eye | Pupil | Reward |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 230629 | 4163 | 50 | 464 | ✅ | ✅ | ✅ | ✅ |
| 230630 | 2942 | 50 | 167 | ✅ | ✅ | ✅ | ✅ |
| 230714 | 16116 | 50 | 589 | ✅ | ✅ | ✅ | ✅ |
| 230719 | 14091 | 50 | 415 | ✅ | ✅ | ✅ | ✅ |
| 230720 | 14454 | 50 | 317 | ✅ | ✅ | ✅ | ✅ |
| 230721 | 15107 | 50 | 277 | ✅ | ✅ | ✅ | ✅ |
| 230816 | 15586 | 50 | 357 | ✅ | ✅ | ✅ | ✅ |
| 230818 | 15972 | 50 | 541 | ✅ | ✅ | ✅ | ✅ |
| 230823 | 18387 | 50 | 368 | ✅ | ✅ | ✅ | ✅ |
| 230825 | 16996 | 50 | 491 | ✅ | ✅ | ✅ | ✅ |
| 230830 | 15645 | 50 | 774 | ✅ | ✅ | ✅ | ✅ |
| 230831 | 16332 | 50 | 584 | ✅ | ✅ | ✅ | ✅ |
| 230901 | 15337 | 50 | 696 | ✅ | ✅ | ✅ | ✅ |

## Multi-Modal Array Status (`.npy`)
All processed data is formatted as `[Trial x Channel/Unit x Sample]`. The standard window is **6000ms** at **1000Hz**.

| Session | SPK | LFP | BEHAV | Notes |
|:---:|:---:|:---:|:---:|:---|
| 230629 | ✅ | ✅ (2) | ✅ | |
| 230630 | ✅ | ✅ (3) | ✅ | |
| 230714 | ✅ | ✅ (2) | ✅ | |
| 230719 | ✅ | ✅ (3) | ✅ | |
| 230720 | ✅ | ✅ (2) | ✅ | |
| 230721 | ✅ | ✅ (2) | ✅ | |
| 230816 | ✅ | ✅ (3) | ✅ | |
| 230818 | ✅ | ✅ (3) | ✅ | |
| 230823 | ✅ | ✅ (3) | ✅ | |
| 230825 | ✅ | ✅ (3) | ✅ | |
| 230830 | ✅ | ✅ (3) | ✅ | |
| 230831 | ✅ | ✅ (3) | ✅ | |
| 230901 | ✅ | ✅ (3) | ✅ | |

## Missing Data & Warnings
- **Session 230630**: Lower unit count compared to other sessions.
- **Session 230901**: Units available for Probe 0 and Probe 2 only (check metadata for details).
- **LFP Coverage**: Most sessions have 2-3 linear probes (128 channels each).
