import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path
import h5py
import numpy as np
import pandas as pd

def find_conda_path():
    # Common paths for Conda installation on Windows
    possible_paths = [
        Path(os.environ.get("USERPROFILE", "")) / "AppData/Local/miniconda3",
        Path(os.environ.get("USERPROFILE", "")) / "anaconda3",
        Path("C:/Users/preprocess-server/anaconda3"),
        Path("C:/ProgramData/miniconda3"),
        Path("C:/ProgramData/anaconda3"),
    ]
    for path in possible_paths:
        if path.exists():
            return str(path)
    return "C:\\Users\\nejath\\AppData\\Local\\miniconda3" # Fallback default

def preprocess_bastoslabvu(raw_dir, output_dir, google_sheet, spike_sorter="kilosort4", cuda="true", slack_api=""):
    print("=" * 60)
    print(" PYPELINE: Starting Bastos Lab Preprocessing Workflow")
    print("=" * 60)
    
    # 1. Normalize paths
    raw_path = str(Path(raw_dir).resolve()).replace("\\", "/") + "/"
    output_path = str(Path(output_dir).resolve()).replace("\\", "/") + "/"
    conda_path = find_conda_path().replace("\\", "/")
    
    package_dir = Path(__file__).parent.resolve()
    matlab_dir = package_dir / "matlab"
    
    repo_path = str(matlab_dir.resolve()).replace("\\", "/") + "/"
    tboxes_path = str((matlab_dir / "forked_toolboxes").resolve()).replace("\\", "/") + "/"
    
    # 2. Write dynamic pipelinePaths.m override
    paths_code = f"""function pp = pipelinePaths(varargin)
pp.DATA_SOURCE  = '{raw_path}';
pp.DATA_DEST    = '{output_path}';
pp.RAW_DATA     = '{raw_path}';
pp.CAT_DATA     = '{output_path}_1_CAT_DATA/';
pp.BIN_DATA     = '{output_path}_2_BIN_DATA/';
pp.SPK_DATA     = '{output_path}_3_SPK_DATA/';
pp.SSC_DATA     = '{output_path}_4_SSC_DATA/';
pp.CNX_DATA     = '{output_path}_5_CNX_DATA/';
pp.NWB_DATA     = '{output_path}_6_NWB_DATA/';
pp.EPO_DATA     = '{output_path}_7_EPO_DATA/';
pp.FIG_DATA     = '{output_path}_9_FIG_DATA/';
pp.CONDA        = '{conda_path}';
pp.REPO         = '{repo_path}';
pp.TBOXES       = '{tboxes_path}';
pp.SCRATCH      = '{output_path}_SCRATCH/';
end
"""
    paths_m_file = matlab_dir / "pipelinePaths.m"
    print(f"Generating temporary path overrides in: {paths_m_file}")
    with open(paths_m_file, "w") as f:
        f.write(paths_code)
        
    # 3. Formulate MATLAB command
    # intan2nwb(ID, IMAGE_TOKEN, varargin)
    slack_arg = f", 'SLACK_ID', '{slack_api}'" if slack_api else ""
    matlab_cmd = f"addpath('{repo_path}'); intan2nwb('{google_sheet}', '', 'skip', false{slack_arg}); exit;"
    
    print(f"Running MATLAB batch command: {matlab_cmd}")
    try:
        subprocess.run(
            ["matlab", "-batch", matlab_cmd],
            cwd=str(matlab_dir),
            check=True
        )
        print("MATLAB preprocessing completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error during MATLAB execution: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'matlab' command not found in systems PATH. Please ensure MATLAB is installed and in PATH.")
        sys.exit(1)
        
    # 4. Find generated NWB files in output_dir/_6_NWB_DATA/ and calculate stats
    nwb_out_dir = Path(output_dir) / "_6_NWB_DATA"
    nwb_files = list(nwb_out_dir.glob("*.nwb"))
    
    if not nwb_files:
        print(f"No generated NWB files found under: {nwb_out_dir}")
        return
        
    for nwb_file in nwb_files:
        print("\n" + "=" * 50)
        print(f" SESSION STATS: {nwb_file.name}")
        print("=" * 50)
        try:
            calculate_and_display_stats(nwb_file)
        except Exception as e:
            print(f"Error parsing stats from {nwb_file.name}: {e}")

def calculate_and_display_stats(nwb_path):
    with h5py.File(nwb_path, "r") as f:
        # 1. Session Duration
        duration_str = "Unknown"
        lfp_group = None
        for k in f.get("acquisition", {}).keys():
            if k.endswith("_lfp"):
                lfp_group = f[f"acquisition/{k}"]
                break
                
        if lfp_group and "timestamps" in lfp_group:
            ts = lfp_group["timestamps"]
            if len(ts) > 0:
                duration_sec = ts[-1] - ts[0]
                mins, secs = divmod(int(duration_sec), 60)
                hours, mins = divmod(mins, 60)
                duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
                
        # 2. Total Kilosorted units & channels
        total_units = 0
        stable_units = 0
        total_channels = 0
        
        if "units" in f:
            total_units = len(f["units/id"])
            if "quality" in f["units"]:
                q_vals = f["units/quality"][:]
                # Convert byte strings if needed
                stable_units = sum(1 for q in q_vals if q == b"1.0" or q == 1.0 or q == "1.0")
                
        if "general/extracellular_ephys/electrodes" in f:
            total_channels = len(f["general/extracellular_ephys/electrodes/id"])
            
        print(f"Kilosort Stats   : {total_units} units ; {stable_units}-stable ; {total_channels} channels")
        
        # 3. Total LFP & MUAe channels
        lfp_chans = 0
        muae_chans = 0
        for k in f.get("acquisition", {}).keys():
            if k.endswith("_lfp"):
                # Data is typically (time, channels)
                shape = f[f"acquisition/{k}/data"].shape
                if len(shape) > 1:
                    lfp_chans += shape[1]
            elif k.endswith("_muae"):
                shape = f[f"acquisition/{k}/data"].shape
                if len(shape) > 1:
                    muae_chans += shape[1]
                    
        print(f"Signal Channels  : LFP: {lfp_chans} channels ; MUAe: {muae_chans} channels")
        print(f"Session Duration : {duration_str}")
        
        # 4. Correct Trials / Condition / Block mapping
        intervals = f.get("intervals", {})
        task_group = None
        for k in intervals.keys():
            g = intervals[k]
            if "trial_num" in g and "task_block_number" in g:
                task_group = k
                break
                
        if task_group:
            g = f[f"intervals/{task_group}"]
            trial_nums = np.array(g["trial_num"][:], dtype=float)
            block_nums = np.array(g["task_block_number"][:], dtype=float)
            cond_nums = np.array(g["task_condition_number"][:], dtype=float)
            correct_vals = np.array(g["correct"][:], dtype=float)
            
            df = pd.DataFrame({
                "trial": trial_nums,
                "block": block_nums,
                "cond": cond_nums,
                "correct": correct_vals
            })
            
            # Unique trials per block/condition
            df_unique = df.drop_duplicates()
            total_correct = int(df_unique["correct"].sum())
            total_trials = len(df_unique)
            
            print(f"Task Name        : {task_group}")
            print(f"Total Trials     : {total_trials} total ; {total_correct} correct")
            print("\nCorrect/Total per Block-Condition:")
            print("-" * 50)
            
            grouped = df_unique.groupby(["block", "cond"])
            for (block, cond), group in grouped:
                correct = int(group["correct"].sum())
                total = len(group)
                print(f"  {correct}/{total} ; B-{int(block):02d} ; C-{int(cond):02d} ; Task-{task_group}")
        else:
            print("Task Trials      : No standard trial/block task intervals found.")
            
def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Pypeline CLI entry point")
    parser.add_argument("--raw_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--google_sheet", required=True)
    parser.add_argument("--spike_sorter", default="kilosort4")
    parser.add_argument("--cuda", default="true")
    parser.add_argument("--slack_api", default="")
    
    args = parser.parse_args()
    preprocess_bastoslabvu(
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        google_sheet=args.google_sheet,
        spike_sorter=args.spike_sorter,
        cuda=args.cuda,
        slack_api=args.slack_api
    )
