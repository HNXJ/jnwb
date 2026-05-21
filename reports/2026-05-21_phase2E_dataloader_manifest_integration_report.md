# DataLoader Manifest Discovery and Contract Integration Report (Phase 2E)

## Purpose
This report documents the design, implementation, and successful testing of Phase 2E: DataLoader manifest discovery and contract integration. It details the integration of metadata contracts and schema validators into `DataLoader`’s discovery path, establishing structured status accessors while maintaining strict execution gating.

## Helper Methods Added
We implemented and tested four core helper methods in `DataLoader`:
1. `DataLoader.get_data_root() -> Path | None`
   - Discovers the environment-configured data path using `OMISSION_DATA_ROOT`.
2. `DataLoader.discover_session_manifest_paths(data_root: Path | None = None) -> list[Path]`
   - Dynamically scans `data_root` recursively for JSON-like metadata manifests, prioritizing dedicated configurations.
3. `DataLoader.load_session_manifest(session_id: str, *, data_root: Path | None = None, allow_fixture: bool = False) -> SessionManifest | None`
   - Scans candidates deterministically, handles multiple options cleanly, applies alias normalization dynamically, and falls back to synthetic fixtures only when explicitly permitted (`allow_fixture=True`).
4. `DataLoader.validate_session_manifest(session_id: str, *, data_root: Path | None = None) -> dict`
   - Performs a complete, non-normalizing validation check on raw metadata manifests to detect unnormalized keys or structural contract drift, returning structured status schemas (`status`, `session_id`, `manifest_path`, `errors`, `warnings`, `truth_status`).

## Candidate Manifest Search Paths
Candidate discovery recursively scans the raw/derived data root in the following hierarchical priority:
1. `<data_root>/manifests/*.json`
2. `<data_root>/metadata/*.json`
3. `<data_root>/session_manifests/*.json`
4. `<data_root>/*.json` (containing "manifest" in the name)
5. `<data_root>/*/*.json` (containing "manifest" in the name)

If multiple candidates are discovered for a single session:
- A deterministic naming preference is applied: first matching `session_{session_id}_manifest.json`, then `{session_id}_manifest.json`, and finally alphabetical fallback.
- The loader logs a warning and flags the validation status as `ambiguous`.

## No-Data Skip Behavior
- If `data_root` is not supplied and the `OMISSION_DATA_ROOT` environment variable is unset, `DataLoader.validate_session_manifest` returns a structured status dictionary with `status="unavailable"`, rather than raising an exception.
- This ensures that local unit tests, CI test runs, and pipeline scripts execute cleanly without crashing due to absent real-world datasets.

## Fixture-vs-Real Boundary
- **Fixture Fallback Gating**: `DataLoader.load_session_manifest` rejects fixture manifests unless `allow_fixture=True`.
- **Misplacement Protection**: `DataLoader.validate_session_manifest` explicitly rejects fixture manifests with `status="invalid"` and appends an error if a fixture manifest is found under a real data root directory (i.e. `expect_real=True`).

## What Raw Data is Explicitly Not Read
- The manifest discovery helpers inspect **only JSON-formatted text files** containing high-level metadata schemas.
- No high-density raw array files, neural voltage matrices, spike-train binaries, or continuous voltage tensors (e.g., NWB, MAT, HDF5, NPY, NPZ) are loaded, read, or modified.

## Remaining Blockers
- **Integration with Real Neural Matrices (Phase 3)**: Downstream loaders still return anonymous/mock arrays when actual files are absent. Integrating high-density arrays with structural manifests is the next scope.
- **Trial-by-Trial Sync**: Matching behavioral omission trials to exact spike timestamps remains unvalidated at the loader interface.

## Truth Status
- **Truth Tier Enforced**: `truth_safe_unverified`
- All metadata-derived files and manifests verified under Phase 2E are strictly locked at `truth_safe_unverified`. No biological, manuscript, or model claims are promoted without receipt verification.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: implementation/contracts / Repo or Workspace: D:\workspace\omission / Date: 2026-05-21
