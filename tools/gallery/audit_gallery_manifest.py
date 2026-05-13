import json
import argparse
from pathlib import Path

def audit_manifest(manifest_path):
    print(f"[audit] Auditing gallery manifest: {manifest_path}")
    if not manifest_path.exists():
        print(f"[error] Manifest not found at {manifest_path}")
        return False

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    items = manifest.get('items', [])
    errors = 0
    warnings = 0
    
    REQUIRED_FIELDS = ['signal_class', 'time_base', 'inference_tier']
    PRIVATE_EXTENSIONS = {'.nwb', '.mat', '.h5', '.hdf5', '.env', '.key'}
    
    for item in items:
        name = item.get('rel_path')
        metadata = item.get('metadata', {})
        
        # 1. Missing Semantic Metadata
        for field in REQUIRED_FIELDS:
            val = metadata.get(field)
            if val in ['unknown', None, '']:
                print(f"[warning] {name}: missing {field}")
                warnings += 1
        
        # 2. Missing Hash
        if not item.get('sha256'):
            print(f"[error] {name}: missing artifact hash")
            errors += 1
            
        # 3. Absolute Paths
        if ':\\' in name or name.startswith('/Users/') or name.startswith('/home/'):
            print(f"[error] {name}: contains absolute Windows/Unix path")
            errors += 1
            
        # 4. Private Files
        if Path(name).suffix.lower() in PRIVATE_EXTENSIONS:
            print(f"[error] {name}: private file extension leaked")
            errors += 1
            
        # 5. Oversized Files (Metadata check)
        if item.get('size', 0) > 25 * 1024 * 1024:
            print(f"[error] {name}: oversized file ({item.get('size')} bytes)")
            errors += 1

        # 6. Public Safe Mismatch
        if item.get('public_safe') and not metadata.get('public_safe', True):
            print(f"[error] {name}: marked public_safe but internal metadata says False")
            errors += 1

    print(f"\n[audit] Results: {errors} Errors, {warnings} Warnings.")
    return errors == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()
    
    success = audit_manifest(Path(args.manifest))
    if not success:
        exit(1)
