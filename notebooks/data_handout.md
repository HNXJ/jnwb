# Downstream Agent Handout: Authoritative Data Topology & File Maps

This document provides a map of the database, file indices, and preprocess directories for Opt OSS agents or external runtimes attempting to locate session inputs.

---

## 1. Primary Raw Dataset Directories

Neural and behavior data resides in these locations on the local workstation:
1. **NWB Directory (`D:/analysis/nwb`)**:
   - Contains 13 session `.nwb` files (sub-C31o and sub-V198o subjects).
   - Filename format: `sub-<subject>_ses-<session>_rec.nwb`.
2. **TFR Array Directory (`D:/workspace/data/tfr_arrays`)**:
   - Contains 720 pre-calculated Time-Frequency Representation (TFR) matrices stored as `.npy` binaries.
   - Filename format: `<subject>_ses-<session>-<probe_letter>-<area>-<condition_code>.npy` (e.g. `sub-C31o_ses-230823-C-FEF-AXAB.npy`).

---

## 2. Derived Indices and Manifests

Indices mapping local channels, cells, and probe geometry are located in these directories:
1. **Vetted Unit Database (`D:/workspace/omission/outputs/publication_figures/grand_database_6040_units.csv`)**:
   - Master list of all 6,040 recorded neurons.
   - Core fields: `session_id`, `unit_id`, `area`, `layer` (putative depth), SNR stability filters (`is_stable`, `stable_plus`), and selectivity metrics (`sig_o_plus`, `sig_s_plus`, `sig_s_minus`).
2. **Layer Masks JSON (`D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr/layer_masks.json`)**:
   - Mapping configuration containing superficial/deep boundary channels based on spectrolaminar mapping (CSD crossover indexes).
   - Structured under key `"by_key"`. Keys are format: `sub-<subject>_ses-<session>|<probe_letter>` (e.g. `sub-C31o_ses-230823|C`).
3. **Data Index Outputs (`D:/workspace/omission/outputs/data_index/batch_13nwb/`)**:
   - Consolidated index files:
     - `unit_address_book_all_sessions.csv` (maps unit index to electrodes).
     - `lfp_session_address_book_all_sessions.csv` (maps electrical channel IDs to probes/areas).
     - `event_timing_inventory_all_sessions.csv` (trial alignments).

---

## 3. Preprocessed LFP Traces Cache

Due to the heavy I/O cost of reading raw TFR maps, the trial-averaged trace data is preprocessed and cached in:
- **Cache Directory**: [outputs/publication_visual_review/tfr_correlations/cache/](file:///D:/workspace/omission/outputs/publication_visual_review/tfr_correlations/cache/)
- **Cached Files**: 22 `.npy` files corresponding to 11 Areas $\times$ 2 Layers (superficial vs. deep).
- **Naming Rule**: `<area>_<layer>_aligned_power.npy` (e.g. `PFC_deep_aligned_power.npy`).
- **Load Logic**: Load directly via `np.load(path)` to skip TFR advanced indexing.

---

## 4. Omission Mappings & Condition Codes

When extracting epochs, align spike and LFP signals to the omission onset (stimulus number 2, where correct trial code == 1). Condition definitions map as follows:

| Condition Category | Condition String | NWB task_condition_number |
| :--- | :--- | :--- |
| **Omission Family A** | AAAB (Control) <br> AXAB (Omission P2) <br> AAXB (Omission P3) | `1`, `2` <br> `3` <br> `4` |
| **Omission Family B** | BBBA (Control) <br> BXBA (Omission P2) <br> BBXA (Omission P3) | `6`, `7` <br> `8` <br> `9` |
| **Omission Family R** | RRRR (Control) <br> RXRR (Omission P2) <br> RRXR (Omission P3) | `11` to `26` <br> `27` to `34` <br> `35`, `37`, `39`, `41` |
