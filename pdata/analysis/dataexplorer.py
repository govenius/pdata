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
import numbers
import datetime

from pdata.analysis.dataview import DataView, PDataSingle
from pdata.helpers import get_keys

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

    print(f"Monitoring {base_dir} for data directories.)")
    print(f"Stop by sending a KeybordInterrupt (in Jupyter, Kernel --> Interrupt kernel).")
    print(f"Waiting for first data set matching filter(s).)")

    pdata_objects = {}
    last_mtimes = {}
    first_plot = True
    while True:
      data_dirs = selector(base_dir, name_filter=name_filter, age_filter=age_filter, return_widget=False)[::-1]

      # Load data from modified data dirs to PDataSingle objects
      latest_mtime = 0
      for dd in data_dirs:
        mtime = get_data_mtime(base_dir, dd)
        if last_mtimes.get(dd, np.nan) != mtime:
          last_mtimes[dd] = mtime
          pdata_objects[dd] = PDataSingle(os.path.join(base_dir, dd))
          latest_mtime = max(mtime, latest_mtime)

      # Release data objects (--> memory) that are no longer going to be plotted
      for dd in list(pdata_objects.keys()):
        if dd not in data_dirs: del pdata_objects[dd]

      # Replot
      if latest_mtime > 0:
        display.clear_output(wait=True)
        fig.clear()

        all_data = list(itertools.chain(ref_data_dirs, [ pdata_objects[dd] for dd in data_dirs ] ))
        plotter(None, all_data, x, y, xlog=xlog, ylog=ylog,
                         slowcoordinate=slowcoordinate,
                         preprocessor=preprocessor, figure=fig)

        display.display(fig)

        print(f"Monitoring {base_dir} for data directories.")
        print(f"Stop by sending a KeybordInterrupt (in Jupyter, Kernel --> Interrupt kernel).")
        print(f"Last dataset change @ {datetime.datetime.fromtimestamp(latest_mtime)}")

      time.sleep(poll_period)

  except KeyboardInterrupt:
    pass
  finally:
    plt.close(fig)

def is_valid_pdata_dir(base_dir, data_dir):
  """ Check whether <base_dir>/<data_dir> is a pdata data set. """
  # Check for presence of a non-empty tabular_data.dat(.gz)
  uncompressed_tabular_dat = os.path.join(base_dir, data_dir, "tabular_data.dat")
  for f in [ uncompressed_tabular_dat+".gz", uncompressed_tabular_dat ]:
    if os.path.isfile(f) and os.path.getsize(f) > 5: return True
  return False # No tabular_data found

def get_data_mtime(base_dir, data_dir, fallback_value=0):
  """Get last modification time of data set in
     <base_dir>/<data_dir>. If the directory appears invalid, return
     fallback_value."""
  for f in ["tabular_data.dat", "tabular_data.dat.gz"]:
    try: return os.path.getmtime( os.path.join(base_dir, data_dir, f) )
    except FileNotFoundError: continue
  return fallback_value

def snapshot_explorer(d, max_depth=10):
  """Graphical dropdown-menu-based helper for creating virtual dimension
     specifications for DataView d. max_depth controls the number of
     dropdown menus.

     In the current implementaion, if you call snapshot_explorer in
     multiple cells, only the most recently created GUI may work
     properly. This is due to use of snapshot_explorer_globals
     effectively as a static variable (see code for details).
  """
  from ipywidgets import interactive, Output, VBox, Dropdown
  from IPython.display import clear_output

  assert max_depth >= 2
  assert len(d.settings()) > 0, 'No snapshots in DataView.'
  snap = d.settings()[0][1]

  # Create the dropdown widgets and text output display
  snapshot_explorer_globals = {}
  snapshot_explorer_globals["out"] = Output()
  snapshot_explorer_globals["dropdowns"] = [ Dropdown(options=(snap.keys() if i==0 else []), index=None) for i in range(max_depth) ]
  snapshot_explorer_globals["recursion_depth"] = 0

  def update_path_selectors():
    """ Update dropdown options. """
    nonlocal snapshot_explorer_globals
    dropdowns = snapshot_explorer_globals["dropdowns"]
    subsnap = snap
    leaf_val = None
    for i in range(1, max_depth):
      prev_key = dropdowns[i-1].value
      #print(f"prev_key = {prev_key}")
      try:
        subsnap = subsnap.get(prev_key, subsnap[get_keys(subsnap)[0]])
        new_options = list(get_keys(subsnap))
        if new_options != list(dropdowns[i].options):
          #print(new_options)
          dropdowns[i].options = new_options
          if len(new_options) > 0: dropdowns[i].index = 0
      except (TypeError,AttributeError,IndexError):
        # subsnap is no longer subscriptable, or is an empty list
        if subsnap is not None: leaf_val = subsnap
        dropdowns[i].options = []
        subsnap = None
        continue
    return leaf_val

  def dtype_spec(val):
    """ Construct dtype specification as string. """
    if val is None: return ""
    if isinstance(val, numbers.Number): return ", dtype=float"
    return ", dtype=str"

  def construct_vdim_spec(change):
    """Update dropdown menu selections and print out the
       d.add_virtual_dimension(...) template based on the selected
       values in the dropdown menus.
    """
    nonlocal snapshot_explorer_globals

    # Avoid recursive updates triggered by update_path_selectors()
    if snapshot_explorer_globals["recursion_depth"] > 0: return
    snapshot_explorer_globals["recursion_depth"] += 1

    def to_str(x): return f"'{x}'" if isinstance(x, str) else str(x)

    with snapshot_explorer_globals["out"]:
      clear_output()
      leaf_val = update_path_selectors()
      print('\nd.add_virtual_dimension(<name>, units=<units>, from_set=['
          + ", ".join(to_str(dd.value) for dd in snapshot_explorer_globals["dropdowns"] if dd.value is not None) + "]"
          + dtype_spec(leaf_val)
          + "))")
      print(f"Value = {leaf_val}  @row==0")

    snapshot_explorer_globals["recursion_depth"] -= 1

  # Add callbacks
  for dd in snapshot_explorer_globals["dropdowns"]: dd.observe(construct_vdim_spec)

  return VBox([ VBox(snapshot_explorer_globals["dropdowns"]), snapshot_explorer_globals["out"] ])
