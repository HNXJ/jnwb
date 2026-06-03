# -*- coding: utf-8 -*-
"""
Created on Wed Jun  7 13:46:32 2023

@author: Patrick, translated from MATLAB by chatgpt-4
"""

import os
import numpy as np

def process_binary_files(NUM_CHANNELS, num_samples, in_file_path, port_letter, file_name):

    # Create a memory-mapped array with the same dtype and shape as data_to_write
    fp = np.memmap(file_name, dtype='int16', mode='w+', shape=(num_samples, NUM_CHANNELS))
    
    for ii in range(NUM_CHANNELS):
        with open(os.path.join(in_file_path, f"amp-{port_letter.upper()}-{ii:03}.dat"), 'rb') as current_file:
            fp[:, ii] = np.fromfile(current_file, dtype=np.int16, count=num_samples)

    del fp  # this line ensures any remaining changes are written to disk before removing the object