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
import pdata.analysis.dataview
from pdata.analysis.dataview import DataView, PDataSingle
from pdata.analysis import dataexplorer

assert pdata.analysis.dataview.FAST_PARSER_ENABLED, "This script assumes that fast_parser is available."

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
def create_data_set(random_values, snapshots=1,
                    compress=True,
                    formatter=None):
  """ Create a dummy dataset. """
  assert len(random_values.shape) == 2, "random values should be a list of tuples"
  assert random_values.shape[1] == 2, "random values should be a list of two-element tuples"

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


# Pregenerate random values
n_rows_pretty = "1M"
n_rows = int(n_rows_pretty[:-1]) * {'M':1000000,'k':1000}[n_rows_pretty[-1]]

random_values = np.random.random((n_rows,2))
random_values[:,1] *= 64

# Run once to avoid constant overheads like loading imports etc.
create_data_set(random_values[:1000,:], snapshots=1)
last_dataset = None

# Create a large dataset with many rows and few snapshots
reps = 1
last_pdatasingle = None
for formatter in ['None', 'lambda x: "%.4e"%x']:
  for compress in [False, True]:
    print(f"Adding {n_rows_pretty} 2-column rows, with format={formatter if formatter!=None else 'default'} and compress={compress}...")
    t = timeit.timeit(f'create_data_set(random_values, compress={compress}, formatter={formatter})',
                      number=reps, globals=globals())/reps
    print(f"  {t:.3f} s per repetition.")

    for fast_parser_enabled in [True, False]:
      pdata.analysis.dataview.FAST_PARSER_ENABLED = fast_parser_enabled

      print(f"Reading it to PDataSingle{' using fast_parser' if fast_parser_enabled else ' using np.genfromtxt'}...")
      t = timeit.timeit(f'global last_pdatasingle; last_pdatasingle = PDataSingle(last_dataset)', number=reps, globals=globals())/reps
      print(f"  {t:.3f} s per repetition.")

      print(f"Converting it to DataView...")
      t = timeit.timeit(f'DataView(last_pdatasingle)', number=reps, globals=globals())/reps
      print(f"  {t:.3f} s per repetition.")

    print("")
