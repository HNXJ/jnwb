import os
import sys
import logging
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
import h5py
import pandas as pd
import numpy as np
from pynwb import NWBHDF5IO

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("jnwb-mcp-server")

# Create FastMCP instance
mcp = FastMCP("jnwb-mcp-server")

@mcp.tool()
def inspect_nwb(file_path: str) -> Dict[str, Any]:
    """
    Inspect the structure and metadata of an NWB file using jnwb.
    
    Args:
        file_path: Absolute or relative path to the .nwb file.
        
    Returns:
        Structured JSON metadata or error dictionary.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_type": "FileNotFound"
        }
        
    try:
        # Extract metadata via PyNWB
        with NWBHDF5IO(str(path), 'r', load_namespaces=True) as io:
            nwb = io.read()
            session_description = str(nwb.session_description) if nwb.session_description else ""
            identifier = str(nwb.identifier) if nwb.identifier else ""
            session_start_time = nwb.session_start_time.isoformat() if nwb.session_start_time else ""
            
        # Extract groups and datasets via h5py to avoid loading all objects
        groups = []
        datasets = []
        neurodata_types = set()
        
        with h5py.File(str(path), 'r') as f:
            # Top-level groups are just the keys of the root file
            groups = list(f.keys())
            
            def visit_item(name, obj):
                ndt = obj.attrs.get("neurodata_type")
                if ndt:
                    ndt_str = ndt.decode() if isinstance(ndt, bytes) else str(ndt)
                    neurodata_types.add(ndt_str)
                    
                if isinstance(obj, h5py.Dataset):
                    datasets.append({
                        "path": "/" + name,
                        "dtype": str(obj.dtype),
                        "shape": list(obj.shape)
                    })
                    
            f.visititems(visit_item)
            
        return {
            "session_description": session_description,
            "identifier": identifier,
            "session_start_time": session_start_time,
            "groups": groups,
            "datasets": datasets,
            "neurodata_types": sorted(list(neurodata_types))
        }
    except Exception as e:
        return {
            "error": f"Failed to parse NWB file: {str(e)}",
            "error_type": "ParseError"
        }

@mcp.tool()
def get_event_codes_and_timings(file_path: str, event_group_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract all event/trial codes and their corresponding sample timestamps from an NWB file using jnwb.
    
    Args:
        file_path: Path to the .nwb file.
        event_group_path: HDF5 path to the events/trials group (e.g., '/intervals/trials' or '/intervals/omission_glo_passive'). Optional.
        
    Returns:
        Structured JSON metadata and list of events or error dictionary.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_type": "FileNotFound"
        }
        
    try:
        event_group_path_resolved = None
        df = None
        
        with NWBHDF5IO(str(path), 'r', load_namespaces=True) as io:
            nwb = io.read()
            
            if event_group_path:
                # Clean prefix / slash if needed
                clean_path = event_group_path.lstrip('/')
                parts = clean_path.split('/')
                if len(parts) >= 2 and parts[0] == 'intervals':
                    name = parts[1]
                    if name in nwb.intervals:
                        df = nwb.intervals[name].to_dataframe()
                        event_group_path_resolved = f"/intervals/{name}"
                    else:
                        return {
                            "error": f"Interval group '{name}' not found under /intervals",
                            "error_type": "PathNotFound"
                        }
            else:
                # Auto-discover
                if nwb.intervals:
                    if 'omission_glo_passive' in nwb.intervals:
                        df = nwb.intervals['omission_glo_passive'].to_dataframe()
                        event_group_path_resolved = '/intervals/omission_glo_passive'
                    elif 'trials' in nwb.intervals:
                        df = nwb.intervals['trials'].to_dataframe()
                        event_group_path_resolved = '/intervals/trials'
                    else:
                        first_name = list(nwb.intervals.keys())[0]
                        df = nwb.intervals[first_name].to_dataframe()
                        event_group_path_resolved = f'/intervals/{first_name}'
                        
        # If not resolved via PyNWB intervals, fall back to direct h5py parsing
        if df is None:
            with h5py.File(str(path), 'r') as f:
                target_path = event_group_path if event_group_path else '/intervals/omission_glo_passive'
                if target_path not in f:
                    # Let's search for any group in intervals
                    if '/intervals' in f:
                        intervals_grp = f['/intervals']
                        if len(intervals_grp.keys()) > 0:
                            target_path = f"/intervals/{list(intervals_grp.keys())[0]}"
                        else:
                            return {
                                "error": "No event or interval groups found in NWB file",
                                "error_type": "PathNotFound"
                            }
                    else:
                        return {
                            "error": "No event or interval groups found in NWB file",
                            "error_type": "PathNotFound"
                        }
                
                obj = f[target_path]
                event_group_path_resolved = target_path
                
                data_dict = {}
                if isinstance(obj, h5py.Dataset):
                    if obj.dtype.names:
                        for name in obj.dtype.names:
                            data_dict[name] = obj[name]
                elif isinstance(obj, h5py.Group):
                    for key in obj.keys():
                        sub_obj = obj[key]
                        if isinstance(sub_obj, h5py.Dataset):
                            data_dict[key] = sub_obj[:]
                            
                if data_dict:
                    df = pd.DataFrame(data_dict)
                    
        if df is None or len(df) == 0:
            return {
                "error": f"Could not extract event data from path: {event_group_path_resolved}",
                "error_type": "ParseError"
            }
            
        # Parse events from DataFrame
        events = []
        code_col = None
        
        # Check standard event code columns
        for col in ['codes', 'code', 'event_code', 'event_codes', 'value', 'type', 'trial_num']:
            if col in df.columns:
                code_col = col
                break
                
        if code_col is None:
            # search for any column containing 'code'
            for col in df.columns:
                if 'code' in col.lower():
                    code_col = col
                    break
                    
        for idx, row in df.iterrows():
            start = float(row['start_time']) if 'start_time' in row and pd.notna(row['start_time']) else 0.0
            stop = float(row['stop_time']) if 'stop_time' in row and pd.notna(row['stop_time']) else None
            
            # Check code value
            code_val = row[code_col] if code_col is not None else idx
            if pd.isna(code_val):
                code_val = "NaN"
            elif isinstance(code_val, (float, int, np.floating, np.integer)):
                if isinstance(code_val, (float, np.floating)) and float(code_val).is_integer():
                    code_val = int(code_val)
                else:
                    code_val = float(code_val)
            else:
                code_val = str(code_val)
                
            events.append({
                "code": code_val,
                "start_time": start,
                "stop_time": stop
            })
            
        return {
            "event_group_path": event_group_path_resolved,
            "events": events,
            "total_events": len(events),
            "time_unit": "seconds"
        }
    except Exception as e:
        return {
            "error": f"Failed to extract events: {str(e)}",
            "error_type": "Unknown"
        }

@mcp.tool()
def prepare_signal_reference(file_path: str, dataset_path: str) -> Dict[str, Any]:
    """
    Prepare a lazy reference to a large electrophysiology or signal dataset WITHOUT loading data into memory.
    
    Args:
        file_path: Path to the .nwb file.
        dataset_path: HDF5 path to the target dataset (e.g., '/acquisition/ElectricalSeries/data').
        
    Returns:
        Structured dataset metadata or error dictionary.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_type": "FileNotFound"
        }
        
    try:
        with h5py.File(str(path), 'r') as f:
            if dataset_path not in f:
                return {
                    "error": f"Dataset path '{dataset_path}' not found in NWB file",
                    "error_type": "PathNotFound"
                }
                
            obj = f[dataset_path]
            if not isinstance(obj, h5py.Dataset):
                return {
                    "error": f"Path '{dataset_path}' is a {type(obj).__name__}, not a dataset",
                    "error_type": "ParseError"
                }
                
            dtype_str = str(obj.dtype)
            shape_list = list(obj.shape)
            chunk_shape = list(obj.chunks) if obj.chunks else None
            compression = str(obj.compression) if obj.compression else None
            
            # Calculate estimated size in MB
            itemsize = obj.dtype.itemsize
            total_elements = 1
            for dim in shape_list:
                total_elements *= dim
            estimated_size_mb = float(total_elements * itemsize) / (1024.0 * 1024.0)
            
            # Build access hint based on dimension shapes
            if len(shape_list) == 2:
                if shape_list[0] > shape_list[1]:
                    access_hint = "Dataset shape is (time, channels). Slice using dataset[start_sample:end_sample, channel_index] or dataset[start_sample:end_sample, :] for all channels."
                else:
                    access_hint = "Dataset shape is (channels, time). Slice using dataset[channel_index, start_sample:end_sample] or dataset[:, start_sample:end_sample] for all channels."
            else:
                access_hint = f"Slice using dataset[...] with indices matching the {len(shape_list)}-dimensional shape."
                
            return {
                "dataset_path": dataset_path,
                "dtype": dtype_str,
                "shape": shape_list,
                "chunk_shape": chunk_shape,
                "compression": compression,
                "estimated_size_mb": estimated_size_mb,
                "access_hint": access_hint
            }
    except Exception as e:
        return {
            "error": f"Failed to prepare signal reference: {str(e)}",
            "error_type": "Unknown"
        }

if __name__ == "__main__":
    # Run the server via standard input/output transport
    mcp.run()
