'''
Module for quick data visualization helpers.

Note that pdata is **not** meant to be a fully-featured plotting utility.
'''

from pdata._metadata import __version__

import os
import re
import time
from pdata.analysis.dataview import DataView, PDataSingle

def data_selector(base_dir, name_filter=".", age_filter=None, max_entries=30, sort_order='chronological', return_widget=True):
  """
  Create an interactive Jupyter selector widget listing all pdata data directories in base_dir,
  with directory name satisfying the regular expression name_filter.

  If return_widget==False, return a list instead.
  """

  # Get list of data dirs
  datadirs = [ n for n in os.listdir(base_dir) if re.search(name_filter, n)!=None and is_valid_pdata_dir(base_dir, n) ]

  # Exclude data dirs that were not recently modified
  if age_filter is not None: datadirs = [ n for n in datadirs if time.time() - get_data_mtime(base_dir, n) < age_filter ]

  # Sort by inverse chronological order
  assert sort_order in ['chronological', 'alphabetical'], f"Unknown sort order: {sort_order}"

  if sort_order=='alphabetical': datadirs = sorted(datadirs)[::-1]
  if sort_order=='chronological': datadirs = sorted(datadirs, key=lambda n: get_data_mtime(base_dir, n))[::-1]

  if not return_widget: return datadirs # Return simple list

  # create the selector widget (to be shown in a Jupyter notebook)
  import ipywidgets
  dataset_selector = ipywidgets.SelectMultiple(options=datadirs, value=datadirs[:1], rows=min(max_entries, len(datadirs)), description="data set")
  dataset_selector.layout.width = "90%"
  return dataset_selector

def basic_plot(base_dir, data_dirs, x, y, xlog=False, ylog=False, slowcoordinate=None, preprocessor=lambda x: x):
  """
  Convenience function for quickly plotting y vs x in each of the pdata data directories, given as strings.

  x, y and slowcoordinate are a column names, specified as strings.

  The data will be plotted as sweeps based on changing value of slowcoordinate, if specified.

  preprocessor is an optional function applied to the DataView object before plotting.
  It can be used to, e.g., add virtual columns.
  """

  # Also accept a single path as a string
  if isinstance(data_dirs, str): data_dirs = [ data_dirs ]

  # Concatenate all specified data dirs into one DataView
  d = DataView([ PDataSingle(os.path.join(base_dir, n)) for n in data_dirs ])

  # Preprocess data (e.g. add virtual dimensions)
  d = preprocessor(d)

  assert x in d.dimensions(), f"{x} is not a column in the data: {data_dirs}"
  assert y in d.dimensions(), f"{y} is not a column in the data: {data_dirs}"
  if slowcoordinate!=None: assert slowcoordinate in d.dimensions(), f"{slowcoordinate} is not a column in the data: {data_dirs}"

  # Plot the results
  import matplotlib
  import matplotlib.pyplot as plt
  
  fig, ax = plt.subplots()

  for s in d.divide_into_sweeps(x if slowcoordinate==None else slowcoordinate):
    dd = d.copy(); dd.mask_rows(s, unmask_instead=True)
    ax.plot(dd[x], dd[y],
            label = None if slowcoordinate==None else f"{dd.single_valued_parameter(slowcoordinate)} {dd.units(slowcoordinate)}" )

  ax.set(xlabel=f'{x} ({dd.units(x)})', ylabel=f'{y} ({dd.units(y)})')

  if xlog: ax.set_xscale('log')
  if ylog: ax.set_yscale('log')

  if slowcoordinate!=None: ax.legend();

  return fig

def is_valid_pdata_dir(base_dir, data_dir):
  """ Check whether <base_dir>/<data_dir> is a pdata data set. """
  return any( os.path.isfile(os.path.join(base_dir, data_dir, f)) for f in ["tabular_data.dat", "tabular_data.dat.gz"] )

def get_data_mtime(base_dir, data_dir, fallback_value=0):
  """Get last modification time of data set in
     <base_dir>/<data_dir>. If the directory appears invalid, return
     fallback_value."""
  for f in ["tabular_data.dat", "tabular_data.dat.gz"]:
    try: return os.path.getmtime( os.path.join(base_dir, data_dir, f) )
    except FileNotFoundError: continue
  return fallback_value
