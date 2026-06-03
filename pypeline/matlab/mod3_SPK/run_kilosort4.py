import sys
import argparse
from pathlib import Path
from kilosort import run_kilosort
from kilosort.io import load_probe

def main():
    parser = argparse.ArgumentParser(description="Run Kilosort 4 from command line")
    parser.add_argument("--filename", type=str, required=True, help="Path to binary file")
    parser.add_argument("--results_dir", type=str, required=True, help="Directory to save results")
    parser.add_argument("--probe_path", type=str, required=True, help="Path to channel map .mat file")
    parser.add_argument("--fs", type=float, required=True, help="Sampling rate")
    
    args = parser.parse_args()
    
    print(f"Loading probe: {args.probe_path}")
    probe = load_probe(args.probe_path)
    
    settings = {
        'fs': args.fs,
        'n_chan_bin': int(probe['n_chan']),
    }
    
    print(f"Running Kilosort 4 settings: {settings}")
    print(f"Input file: {args.filename}")
    print(f"Results dir: {args.results_dir}")
    
    run_kilosort(
        settings=settings,
        probe=probe,
        filename=Path(args.filename),
        results_dir=Path(args.results_dir)
    )
    print("Kilosort 4 run completed successfully.")

if __name__ == "__main__":
    main()
