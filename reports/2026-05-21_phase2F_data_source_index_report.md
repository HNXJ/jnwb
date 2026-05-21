# DataSourceIndex and raw-array boundary scaffolds Report (Phase 2F)

## Purpose
This report documents the design, implementation, and validation of Phase 2F: gated `DataSourceIndex` and raw-array boundary scaffolds. We have established a robust, lightweight discovery contract that allows scanning, classifying, and validating file-level availability of experimental datasets under `OMISSION_DATA_ROOT` without opening or reading high-density neural array payloads.

## DataSourceIndex and DataSourceRecord Fields

### DataSourceRecord
Defines a structured, single-file metadata schema containing the following fields:
- `path`: str (absolute path to the candidate file)
- `session_id`: Optional[str] (parsed 6-digit session string, or "fixture" for synthetic configs)
- `signal_class`: Optional[str] (token-matched signal type: "SPK", "MUAe", "LFP", "behavior", or None)
- `file_type`: str (file extension, e.g., `.json`, `.npy`, `.nwb`)
- `size_bytes`: Optional[int] (file size in bytes from directory/NTFS metadata only)
- `role`: str (classified role: "manifest", "metadata", "raw_neural_array", "behavior", or "unknown")
- `readable_for_phase2`: bool (gated read authorization; False for all raw neural matrices)
- `reason_not_read`: Optional[str] (explanation for blocked/unreadable status)
- `source_status`: str (discovery status: "discovered_metadata", "discovered_manifest", "discovered_raw_blocked", "unavailable", "skipped_large_or_raw", "invalid", "ambiguous")
- `warnings`: list[str] (any validation or classification warnings)
- `truth_status`: str = "truth_safe_unverified" (enforced metadata validation safety tier)

### DataSourceIndex
Represents a collection-level manifest containing:
- `data_root`: Optional[str] (path to the raw data root scanned)
- `records`: list[DataSourceRecord] (discovered source files)
- `warnings`: list[str] (global scanner warnings)
- `errors`: list[str] (global scanner errors, e.g., missing data root)
- `truth_status`: str = "truth_safe_unverified"

## Scanned Subfolders
To ensure speed and prevent deep recursion issues on high-density storage drives, the discovery scanning behavior is strictly bounded to the root and these shallow subfolders:
- `manifests/`
- `metadata/`
- `session_manifests/`
- `behavior/`
- `arrays/`
- `nwb/`

## Blocked Raw Extensions
The contract enforces a strict **no-read policy** for raw array payloads. The following raw extensions are automatically identified, classified as role `raw_neural_array`, assigned status `discovered_raw_blocked`, and gated from any active parsing or reads:
- `.nwb`
- `.mat`
- `.h5`
- `.hdf5`
- `.npy`
- `.npz`

## No-Read Guarantee
No file-read, array-load, or custom format parsing was executed on any binary datasets. All file existence checks, name parsing, and sizing are retrieved strictly through shallow directory metadata queries (`Path.stat().st_size` and `os.scandir`). This guarantees zero risk of reading incomplete array blocks or corrupting file memory during testing.

## Remaining Blockers
- **Fixture SignalBlock Loading (Phase 2G)**: Next steps require utilizing the DataSourceIndex to instantiate mock/fixture-backed `SignalBlock` loaders so pipeline components can validate multi-channel operations.
- **Raw Matrix Gated Reading (Phase 3)**: Safe accessors for low-level mmap block reads of large `.npy`/`.nwb` payloads remain gated behind later phases.

## Truth Status
- **Truth Tier Enforced**: `truth_safe_unverified`
- All files, indices, and records remain under the strict `truth_safe_unverified` safety status. No biological, manuscript, or model claims are promoted without receipt verification.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: implementation/contracts / Repo or Workspace: D:\workspace\omission / Date: 2026-05-21
