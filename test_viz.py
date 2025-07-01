# -*- coding: utf-8 -*-
"""
Created on Tue Jul  1 16:33:09 2025

@author: AD
"""

from fastf1 import get_session
from visualization import top_speed_comparison, sector_gap

# Load the FP1 session for Austria 2025
sess = get_session(2025, "Austria", "FP1")
sess.load()

# Define where to save
out_dir = "visualization/2025_Austria/FP1"
from pathlib import Path
Path(out_dir).mkdir(parents=True, exist_ok=True)

# Run and save plots
top_speed_comparison(sess, f"{out_dir}/top_speed.png")
sector_gap(sess, f"{out_dir}/compare.png")

print("Plots saved successfully!")
