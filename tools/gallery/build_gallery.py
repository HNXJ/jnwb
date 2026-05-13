import os
import sys
import json
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

class GalleryBuilder:
    ALLOWED_EXTENSIONS = {'.html', '.png', '.jpg', '.jpeg', '.svg', '.pdf', '.json', '.csv'}
    BLACK_LIST_FILES = {'.nwb', '.mat', '.h5', '.hdf5', '.env', '.key', '.token', '.heapsnapshot'}
    
    # Metadata Inference Keywords (Conservative Fallbacks)
    KEYWORDS = {
        'signal_class': {
            'LFP': ['lfp', 'tfr', 'spectrogram', 'theta', 'alpha', 'beta', 'gamma'],
            'SPK/SUA': ['spk', 'sua', 'psth', 'unit', 'firing'],
            'MUAe': ['muae'],
            'behavior': ['pupil', 'eye', 'lick', 'lever'],
            'metadata': ['registry', 'manifest', 'audit', 'status']
        },
        'time_base': {
            'p1_relative': ['p1', 'full_sequence'],
            'omission_relative': ['omission_relative', 'omrel', 'px', 'px', 'p2', 'p3', 'p4']
        },
        'inference_tier': {
            'descriptive_channel_level': ['lfp', 'muae', 'tfr'],
            'unit_level_session_summarized': ['spk', 'sua', 'unit']
        }
    }

    def __init__(self, source, out, title, public_safe=False):
        self.source = Path(source)
        self.out = Path(out)
        self.title = title
        self.public_safe = public_safe
        self.manifest_path = self.out / "manifests" / "gallery_manifest.json"
        self.items = []
        self.session_manifests = self._load_all_session_manifests()

    def _load_all_session_manifests(self):
        manifests = {}
        manifest_dir = Path(__file__).parent.parent.parent / "artifacts" / "manifests"
        if manifest_dir.exists():
            for f in manifest_dir.glob("session_*_manifest.json"):
                try:
                    with open(f, 'r') as f_in:
                        data = json.load(f_in)
                        manifests[data['session_id']] = data
                except Exception as e:
                    print(f"[warning] Failed to load session manifest {f}: {e}")
        return manifests

    def extract_session_id(self, path_str):
        import re
        # Look for 6-digit session ID pattern
        match = re.search(r'(23[0-9]{4})', path_str)
        if match:
            return match.group(1)
        return None

    def compute_sha256(self, file_path):
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def infer_metadata(self, filename, parent_folders):
        name_lower = filename.lower()
        context = " ".join([str(f).lower() for f in parent_folders] + [name_lower])
        
        metadata = {
            'signal_class': 'unknown',
            'time_base': 'unknown',
            'inference_tier': 'unknown',
            'analysis_family': 'unknown'
        }
        
        # Simple analysis family inference
        analysis_keywords = {
            'SFC': ['sfc', 'ppc'],
            'Granger': ['granger'],
            'TFR': ['tfr', 'spectrogram'],
            'PSTH': ['psth'],
            'Decoding': ['decoding']
        }
        for family, kws in analysis_keywords.items():
            if any(kw in context for kw in kws):
                metadata['analysis_family'] = family
                break

        for category, mappings in self.KEYWORDS.items():
            for tag, kw_list in mappings.items():
                if any(kw in context for kw in kw_list):
                    metadata[category] = tag
                    break
        
        return metadata

    def load_adjacent_metadata(self, file_path):
        """Looks for figure_manifest.json, manifest.json, or meta.json in the same directory."""
        search_names = ['figure_manifest.json', 'manifest.json', 'meta.json', 'parameters.json']
        parent = file_path.parent
        for name in search_names:
            meta_path = parent / name
            if meta_path.exists():
                try:
                    with open(meta_path, 'r') as f:
                        data = json.load(f)
                    # If it's a list (like f048 manifest), find the entry for this file
                    if isinstance(data, list):
                        for entry in data:
                            if entry.get('filename') == file_path.name or entry.get('path') == file_path.name:
                                return entry
                    # If it's a dict, use it directly (or look for a key matching the filename)
                    elif isinstance(data, dict):
                        if file_path.name in data:
                            return data[file_path.name]
                        return data
                except Exception as e:
                    print(f"[warning] Failed to parse metadata at {meta_path}: {e}")
        return {}

    def security_audit(self, file_path):
        """Returns True if the file is safe to include."""
        if file_path.suffix.lower() in self.BLACK_LIST_FILES:
            return False
        if any(secret in file_path.name.lower() for secret in ['credential', 'key', 'token', 'secret', '.env']):
            return False
        
        # GitHub File Size Policy Hard Limit (>25MB skip)
        if file_path.stat().st_size > 25 * 1024 * 1024:
            print(f"[warning] Skipping oversized file: {file_path}")
            return False

        # Small CSV check
        if file_path.suffix.lower() == '.csv':
            if file_path.stat().st_size > 1024 * 1024: # 1MB limit for CSV
                return False
        return True


    def build(self):
        print(f"[action] Building gallery: {self.title}")
        print(f"[action] Source: {self.source}")
        print(f"[action] Output: {self.out}")

        # Prep directories
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "assets").mkdir(exist_ok=True)
        (self.out / "manifests").mkdir(exist_ok=True)
        (self.out / "figures").mkdir(exist_ok=True)

        # 1. Copy Assets
        src_root = Path(__file__).parent.parent.parent / "gallery_src"
        shutil.copy(src_root / "style.css", self.out / "assets" / "style.css")
        shutil.copy(src_root / "gallery.js", self.out / "assets" / "gallery.js")
        
        # 2. Scan and Copy Figures
        for root, _, files in os.walk(self.source):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() not in self.ALLOWED_EXTENSIONS:
                    continue
                
                if not self.security_audit(file_path):
                    print(f"[warning] Skipping unsafe file: {file_path}")
                    continue

                rel_path_in_source = file_path.relative_to(self.source)
                dest_path = self.out / "figures" / rel_path_in_source
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy(file_path, dest_path)
                
                # 2.3 Metadata Enrichment
                inferred = self.infer_metadata(file_path.name, rel_path_in_source.parents[:-1])
                explicit = self.load_adjacent_metadata(file_path)
                
                # Merge: explicit overrides inferred
                item_metadata = {**inferred, **explicit}

                # Attach Session Metadata
                session_id = self.extract_session_id(str(rel_path_in_source))
                if session_id and session_id in self.session_manifests:
                    item_metadata['session_id'] = session_id
                    item_metadata['subject_id'] = self.session_manifests[session_id].get('subject_id')
                    item_metadata['truth_status'] = self.session_manifests[session_id].get('truth_status')
                
                # Ensure all semantic fields exist
                semantic_fields = [
                    'signal_class', 'time_base', 'inference_tier', 'analysis_family',
                    'baseline_ms', 'contrast', 'alignment_event', 'validation_status'
                ]
                warnings = []
                for field in semantic_fields:
                    if field not in item_metadata or item_metadata[field] in ['unknown', None]:
                        if field in ['signal_class', 'time_base', 'inference_tier']:
                            warnings.append(f"missing_{field}")

                # Index
                rel_url = f"figures/{rel_path_in_source.as_posix()}"
                self.items.append({
                    "name": item_metadata.get('title') or file_path.stem.replace("_", " ").title(),
                    "rel_path": rel_url,
                    "type": file_path.suffix[1:].lower(),
                    "sha256": self.compute_sha256(file_path),
                    "metadata": item_metadata,
                    "size": file_path.stat().st_size,
                    "warnings": warnings,
                    "public_safe": self.public_safe
                })

        # 3. Write Manifest
        manifest = {
            "title": self.title,
            "generated_at": datetime.now().isoformat(),
            "items": self.items
        }
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        # 4. Generate HTML
        template_path = src_root / "template.html"
        with open(template_path, "r") as f:
            template = f.read()
        
        html_content = template.replace("{{ title }}", self.title)
        
        with open(self.out / "index.html", "w") as f:
            f.write(html_content)
        
        # 5. .nojekyll
        (self.out / ".nojekyll").touch()

        print(f"[action] SUCCESS: Indexed {len(self.items)} items.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", default="gallery_dist/gallery")
    parser.add_argument("--title", default="Omission Project Gallery")
    parser.add_argument("--public-safe", action="store_true")
    args = parser.parse_args()

    builder = GalleryBuilder(args.source, args.out, args.title, args.public_safe)
    builder.build()
