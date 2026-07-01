import h5py
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
from pynwb import NWBHDF5IO
from jnwb.mcp_server.server import mcp

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
                        
        if df is None:
            with h5py.File(str(path), 'r') as f:
                target_path = event_group_path if event_group_path else '/intervals/omission_glo_passive'
                if target_path not in f:
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
            
        events = []
        code_col = None
        
        for col in ['codes', 'code', 'event_code', 'event_codes', 'value', 'type']:
            if col in df.columns:
                code_col = col
                break
                
        if code_col is None:
            for col in df.columns:
                if 'code' in col.lower():
                    code_col = col
                    break
                    
        for idx, row in df.iterrows():
            start = float(row['start_time']) if 'start_time' in row and pd.notna(row['start_time']) else 0.0
            stop = float(row['stop_time']) if 'stop_time' in row and pd.notna(row['stop_time']) else None
            
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
