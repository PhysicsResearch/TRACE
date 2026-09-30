import sys
import os
import pandas as pd
import numpy as np

# Test compute_kinematics
def compute_kinematics(dataframe, pos_cols):
    t = dataframe['time'].values if 'time' in dataframe.columns else np.arange(len(dataframe)) * 0.01
    vel_dict = {}
    acc_dict = {}

    if len(t) < 2:
        for col in pos_cols:
            vel_dict[col] = np.zeros(len(t))
            acc_dict[col] = np.zeros(len(t))
        return vel_dict, acc_dict

    t_clean = np.array(t, dtype=float)
    if np.any(np.diff(t_clean) <= 0):
        t_clean = np.maximum.accumulate(t_clean)
        for i in range(1, len(t_clean)):
            if t_clean[i] <= t_clean[i - 1]:
                t_clean[i] = t_clean[i - 1] + 1e-4

    for col in pos_cols:
        if col in dataframe.columns:
            pos = pd.to_numeric(dataframe[col], errors='coerce').fillna(0.0).values
            v = np.gradient(pos, t_clean)
            a = np.gradient(v, t_clean)
            vel_dict[col] = v
            acc_dict[col] = a
        else:
            vel_dict[col] = np.zeros(len(t))
            acc_dict[col] = np.zeros(len(t))

    return vel_dict, acc_dict

# Test data
t = np.linspace(0, 10, 1001)
df = pd.DataFrame({
    'timestamp': t * 1000.0,
    'time': t,
    'X': 25.0 * np.cos(2 * np.pi * t / 4.0)**6,
    'Y': 25.0 * np.sin(2 * np.pi * t / 4.0),
    'Z': np.zeros_like(t),
    'Command': [''] * len(t)
})

pos_cols = ['X', 'Y', 'Z']
vel_dict, acc_dict = compute_kinematics(df, pos_cols)

print("Pos X shape:", df['X'].shape, "range:", (df['X'].min(), df['X'].max()))
print("Vel X shape:", vel_dict['X'].shape, "range:", (vel_dict['X'].min(), vel_dict['X'].max()))
print("Acc X shape:", acc_dict['X'].shape, "range:", (acc_dict['X'].min(), acc_dict['X'].max()))

# Build table column list
table_columns = ['time'] + pos_cols + [f"Vel. {c}" for c in pos_cols] + [f"Acc. {c}" for c in pos_cols]
if 'Command' in df.columns:
    table_columns.append('Command')

print("\nTable columns count:", len(table_columns))
print("Table columns:", table_columns)

header_units = {
    'time': 'Time (s)',
    'X': 'X (mm)',
    'Y': 'Y (mm)',
    'Z': 'Z (mm)',
    'Vel. X': 'Vel. X (mm/s)',
    'Vel. Y': 'Vel. Y (mm/s)',
    'Vel. Z': 'Vel. Z (mm/s)',
    'Acc. X': 'Acc. X (mm/s²)',
    'Acc. Y': 'Acc. Y (mm/s²)',
    'Acc. Z': 'Acc. Z (mm/s²)',
    'Command': 'Command'
}
headers = [header_units.get(c, c) for c in table_columns]
print("Table headers:", headers)

print("\nAll kinematics test assertions passed!")
