"""
Timing tests for qualitatively checking performance.
"""

import logging
import os
import shutil
import tempfile
import time
import io
import datetime

import timeit

import numpy as np
import numpy.random

from pdata.procedural_data import run_measurement
from pdata.analysis.dataview import DataView, PDataSingle
from pdata.analysis import dataexplorer

data_root = tempfile.mkdtemp(prefix='pdata_timing_test_')

def get_instrument_snapshot():
  """ Fake snapshot of instrument parameters. """
  return { 'instruments': {
      "VNA1": { "power": -10, "RBW": 10e3,
                "random_scalar": np.random.randn(),
                "random_list": np.random.randn(10).tolist(),
                "random_ndarray": np.random.randn(10)
               },
      "voltage_source1": { "V": -1.234 },
      "voltage_source2": { "V": -5.678 },
    } }

last_dataset = None
def create_data_set(snapshots=1, inner_repetitions=100000,
                    compress=True,
                    formatter=None):
  """ Create a dummy dataset. """
  random_values = np.random.random((inner_repetitions,2))

  cols = [["X",""], ["Y",""]]
  if formatter is not None:
    for c in [0,1]: cols[c].append(formatter)

  with run_measurement(get_instrument_snapshot,
                       columns=cols,
                       name='large-dataset',
                       data_base_dir=data_root,
                       compress=compress) as m:

    start_time = time.time()
    for s in range(snapshots):
      m.add_points({'X': random_values[:,0], 'Y': random_values[:,1]})

  global last_dataset
  last_dataset = m.path()
  return m.path()


# Run once to avoid constant overheads like loading imports etc.
create_data_set(snapshots=1, inner_repetitions=10)

# Create a large dataset with many rows and few snapshots
reps = 2
for formatter in ['None', 'lambda x: "%.4e"%x']:
  for compress in [False, True]:
    print(f"Adding 100k rows, with formatter={formatter} and compress={compress}...")
    t = timeit.timeit(f'create_data_set(compress={compress},formatter={formatter})', number=reps, globals=globals())/reps
    print(f"  {t:.3f} s per repetition.")

    print(f"Reading it to PDataSingle...")
    t = timeit.timeit(f'PDataSingle(last_dataset)', number=reps, globals=globals())/reps
    print(f"  {t:.3f} s per repetition.")

    print(f"Reading it to PDataSingle and then converting to DataView...")
    t = timeit.timeit(f'DataView(PDataSingle(last_dataset))', number=reps, globals=globals())/reps
    print(f"  {t:.3f} s per repetition.")

    print("")
