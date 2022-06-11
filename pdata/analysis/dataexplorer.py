'''
Module for quick data visualization helpers.

Note that pdata is **not** meant to be a fully-featured plotting utility.
'''

from pdata._metadata import __version__

import os
import re
import time
import itertools
import logging
import numpy as np

from pdata.analysis.dataview import DataView, PDataSingle

from IPython import display

import matplotlib
import matplotlib.pyplot as plt

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

def basic_plot(base_dir, data_dirs, x, y, xlog=False, ylog=False, slowcoordinate=None, preprocessor=lambda x: x, figure=None):
  """
  Convenience function for quickly plotting y vs x in each of the pdata data directories.

  data_dirs should be an array of PDataSingle objects or paths, given as strings relative to base_dir.
  data_dirs can also be a single string or single PDataSingle object.

  x, y and slowcoordinate are a column names, specified as strings.

  The data will be plotted as sweeps based on changing value of slowcoordinate, if specified.

  preprocessor is an optional function applied to the DataView object before plotting.
  It can be used to, e.g., add virtual columns.

  An existing pyplot figure can be optionally specified. It is first cleared.

  Returns the create/reused figure object.
  """

  # Also accept a single path as a string
  if isinstance(data_dirs, str) or isinstance(data_dirs, PDataSingle):
    data_dirs = [ data_dirs ]

  # Concatenate all specified data dirs into one DataView
  d = DataView([ PDataSingle(os.path.join(base_dir, n)) if isinstance(n, str) else n for n in data_dirs ])

  # Preprocess data (e.g. add virtual dimensions)
  if preprocessor is not None: d = preprocessor(d)

  assert x in d.dimensions(), f"{x} is not a column in the data: {data_dirs}"
  assert y in d.dimensions(), f"{y} is not a column in the data: {data_dirs}"
  if slowcoordinate!=None: assert slowcoordinate in d.dimensions(), f"{slowcoordinate} is not a column in the data: {data_dirs}"

  # Plot the results
  fig, ax = plt.subplots(num=figure, clear=True)

  for s in d.divide_into_sweeps(x if slowcoordinate==None else slowcoordinate):
    dd = d.copy(); dd.mask_rows(s, unmask_instead=True)
    ax.plot(dd[x], dd[y],
            label = None if slowcoordinate==None else f"{dd.single_valued_parameter(slowcoordinate)} {dd.units(slowcoordinate)}" )

  ax.set(xlabel=f'{x} ({dd.units(x)})', ylabel=f'{y} ({dd.units(y)})')

  if xlog: ax.set_xscale('log')
  if ylog: ax.set_yscale('log')

  if slowcoordinate!=None: ax.legend();

  return fig

def monitor_dir(base_dir, x, y,
                name_filter='.', age_filter=None,
                xlog=False, ylog=False, slowcoordinate=None, preprocessor=lambda x: x,
                selector=data_selector, plotter=basic_plot,
                ref_data_dirs=[],
                poll_period=3):
  """Monitor base_dir for new data matching selector(base_dir,
     name_filter, age_filter), until interrupted by
     KeyboardInterrupt.

     If new data is found, plot y vs x using plotter(<array of
     PDataSingle>, x, y, xlog, ylog, slowcoordinate, preprocessor).

     The default selector and plotter functions can be overriden. They
     should accept the same arguments as data_selector() and
     basic_plot(), respectively.

     ref_data_dirs can be used to specify data sets that are always
     plotted. These should be given as full paths (not relative to
     base_dir), or as PDataSingle objects.

     poll_period specifies how often base_dir is checked for changes.
     Specified in seconds.
  """
  fig = plt.figure()

  try:
    # Convert all reference data dirs to PDataSingle objects
    ref_data_dirs = [ PDataSingle(n) if isinstance(n, str) else n for n in ref_data_dirs ]

    pdata_objects = {}
    last_mtimes = {}
    while True:
      data_dirs = selector(base_dir, name_filter=name_filter, age_filter=age_filter, return_widget=False)[::-1]

      # Load data from modified data dirs to PDataSingle objects
      no_changes = True
      for dd in data_dirs:
        mtime = get_data_mtime(base_dir, dd)
        if last_mtimes.get(dd, np.nan) != mtime:
          last_mtimes[dd] = mtime
          pdata_objects[dd] = PDataSingle(os.path.join(base_dir, dd))
          no_changes = False

      # Release data objects (--> memory) that are no longer going to be plotted
      for dd in pdata_objects.keys():
        if dd not in data_dirs: del pdata_objects[dd]

      # Replot
      if not no_changes:
        display.clear_output(wait=True)
        all_data = list(itertools.chain(ref_data_dirs, [ pdata_objects[dd] for dd in data_dirs ] ))
        plotter(None, all_data, x, y, xlog=xlog, ylog=ylog,
                         slowcoordinate=slowcoordinate,
                         preprocessor=preprocessor, figure=fig)
        display.display(fig)
        print(f"Monitoring {base_dir} for data directories. Stop by sending a KeybordInterrupt (in Jupyter, Kernel --> Interrupt kernel).")

      time.sleep(poll_period)

  except KeyboardInterrupt:
    pass
  finally:
    plt.close(fig)

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
