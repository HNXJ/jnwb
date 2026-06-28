import h5py
from pathlib import Path
from typing import Dict, Any
from pynwb import NWBHDF5IO
from jnwb.mcp_server.server import mcp

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
