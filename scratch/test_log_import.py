import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, r"c:\TRACE")

from fcn_plan.fcn_import import is_trace_log_file, detect_file_format, parse_trace_log_file, match_log_axis_name

sample_log = r"c:\TRACE\scratch\sample_log.txt"

print("--- 1. Testing Format Detection ---")
is_log = is_trace_log_file(sample_log)
fmt = detect_file_format(sample_log)
print(f"is_trace_log_file: {is_log}")
print(f"detect_file_format: {fmt}")
assert is_log is True, "Expected is_trace_log_file to be True"
assert fmt == 'trace_log', f"Expected format 'trace_log', got '{fmt}'"

print("\n--- 2. Testing Axis Matching ---")
for col in ['Time_s', 'Pos_X_mm', 'Pos_Y_mm', 'Pos_Z_mm', 'Probe', 'Pos_LAT_mm', 'Pos_SI_mm', 'Pos_AP_mm', 'Pos_Roll_deg']:
    matched = match_log_axis_name(col)
    print(f"  {col:15s} -> {matched}")

assert match_log_axis_name('Pos_X_mm') == 'X'
assert match_log_axis_name('Pos_Y_mm') == 'Y'
assert match_log_axis_name('Pos_Z_mm') == 'Z'
assert match_log_axis_name('Probe') is None, "Probe MUST be None (excluded)"
assert match_log_axis_name('Time_s') == 'time'

print("\n--- 3. Testing parse_trace_log_file ---")
plan_df, device, matched_axes, probe_detected, orig_count, t_max = parse_trace_log_file(sample_log)

print(f"Detected Device: {device}")
print(f"Matched Axes: {matched_axes}")
print(f"Probe Detected: {probe_detected}")
print(f"Original Points: {orig_count}")
print(f"Duration: {t_max:.2f} s")
print(f"Plan DataFrame Columns: {list(plan_df.columns)}")
print(f"Plan DataFrame Shape: {plan_df.shape}")
print(f"Null count in Plan DF:\n{plan_df.isnull().sum()}")

assert device == "Lung Phantom", f"Expected 'Lung Phantom', got '{device}'"
assert 'X' in matched_axes and 'Y' in matched_axes and 'Z' in matched_axes
assert 'Probe' not in plan_df.columns, "Probe MUST NOT be in plan_df"
assert 'timestamp' in plan_df.columns and 'time' in plan_df.columns
assert 'Command' in plan_df.columns
assert len(plan_df) > 0
assert not plan_df.isnull().any().any(), "Plan dataframe must not contain any NaNs"

print("\nAll unit tests passed successfully!")
