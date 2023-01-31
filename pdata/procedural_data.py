"""
Class for storing measurement data.
"""

from pdata._metadata import __version__

import os
import sys
import numpy as np
import time
import datetime
import logging
import shutil
import gzip
import tarfile
import contextlib
import json
import jsondiff
import tempfile
import random
import re

from pdata.helpers import NumpyJSONEncoder, preprocess_snapshot, PdataJSONDiffer
import pdata.jupyter_helpers

# Version number of the data format written to disk, following Semantic Versioning (https://semver.org/).
# This version number should increase much more slowly than the pdata package/release versions.
ondisk_format_version = (1, 0, 0)

@contextlib.contextmanager
def run_measurement(get_snapshot,
                    columns, name,
                    data_base_dir='.',
                    dir_name_generator=lambda n: datetime.datetime.now().strftime(f"%Y-%m-%d_%H-%M-%S_{int(1e3*random.random())}") + f"_{n}",
                    autosnap=True, snap_diff_filter=preprocess_snapshot,
                    compress=True, log_level="inherit"):
  '''
  A simple context manager that runs begin() and end()
  automatically, and gets an updated snapshot of instrument parameters
  each time data is added, using get_snapshot().

  See docstring of Measurement.__init__ for definition of most arguments.

  The directory name for storing the data set is:
    <data_base_dir>/<dir_name_generator(name)>

  By default, we filter out timestamps added by QCoDeS from snapshot diffs.

  If you're using QCoDeS, your get_snapshot function would typically look like this::

    import qcodes.station
    with run_measurement(lambda s=qcodes.station.Station.default: s.snapshot(update=True), ...) as m:
      ...
  
  '''
  target_dir = os.path.join(data_base_dir, dir_name_generator(name))

  m = Measurement(columns,
                  target_dir=target_dir,
                  get_snapshot=get_snapshot,
                  snap_diff_filter=snap_diff_filter,
                  autosnap=autosnap, compress=compress)

  m.begin()
  try:     yield m
  finally: m.end()



class Measurement():
  '''
  Writes data to a data table with fixed columns defined during __init__().

  The data directory contains the following:

    * :file:`tabular_data.dat` -- Data table with rows added using :code:`add_points`, and columns defined as arguments of :code:`run_measurement`.
    * :file:`snapshot.json` -- Instrument parameter snapshot when :code:`run_measurement` started.
    * :file:`snapshot.row-<n>.diff<m>.json` -- `jsondiff <https://pypi.org/project/jsondiff/>`_ of parameter changes, recorded when the there were <n> data rows in tabular_data.dat. <m> is a simple counter, in case multiple diffs are created for the same row.
    * :file:`log.txt` -- copy of messages from the logging module.
    * A copy of the Jupyter notebook (.ipynb) or other measurement script, if possible.

  Optionally, the files may be compressed (.gz or .tar.gz).

  Although the format is human-readable in the simplest cases, it is
  meant to be parsed programmatically, i.e., by the dataview module
  (analysis/dataview.py).

  For more information, see https://pdata.readthedocs.io/en/latest/
  '''

  def __init__(self, columns, target_dir=None, get_snapshot=None,
               autosnap=True, snap_diff_filter=None, omit_readme=False,
               compress=True, log_level="inherit"):
    '''Args:

      columns: a list of strings (column names) or tuples (<column
               name>, <units> [optional], <formatter> [optional],
               <dtype> [optional]).  Formatter should be a function
               that takes in a data point and turns it into a str
               written to the data file.  Dtype should be a data type
               class (e.g. float). analysis.dataview.PDataSingle will
               use it as a hint while reading the data.

      target_dir: full path to where the data directory is to be created.

      get_snapshot: function that returns a dict of instrument settings.

      autosnap: create snapshot diffs automatically each time add_points()
                is called.

      snap_diff_filter: function applied to the snapshot before computing diffs;
                        useful for filtering things out (e.g. timestamps).

      omit_readme: don't create a README file in the data directory.

      compress: compress data files when measurement ends

      log_level: log level for log.txt stored in the data
                 directory. If "inherit", logging.getLogger().level is
                 used.
    '''
    self._target_dir = target_dir
    self._get_snapshot = get_snapshot
    self._autosnap = True
    self._snap_diff_filter = snap_diff_filter
    self._omit_readme = omit_readme
    self._compress = compress
    self._log_level = log_level

    self._npoints_total = 0
    self._last_snapshot = None
    self._snapshot_diff_rows = []

    self._columns = list()
    self._units = list()
    self._formatters = list()
    self._dtypes = list()

    self._check_for_manual_abort()

    # Parse columns and units.
    # Units are optional.
    # The formatter is an optional function used for conversion to str.
    # The data type is an optional data type spec saved as metadata in tabular_data
    for x in columns:
      u = ""
      f = None
      dt = None
      if isinstance(x, str):
        c = x
      elif len(x) == 2:
        c,u = x
      elif len(x) == 3:
        c,u,f = x
      elif len(x) == 4:
        c,u,f,dt = x
      else:
        raise Exception('Did not understand column specification: %s' % x)

      from pdata.analysis.dataview import column_name_regex, column_unit_regex
      assert re.match(f"^{column_name_regex}$", c) != None, f"Column name '{c}' contains unexpected characters. It does not match the regular expression '^{column_name_regex}$'."
      assert re.match(f"^{column_unit_regex}$", u) != None, f"Unit '{u}' for column '{c}' contains unexpected characters. It does not match the regular expression '^{column_unit_regex}$'."

      self._columns.append(c)
      self._units.append(u)
      self._formatters.append(f)
      self._dtypes.append(dt)

      assert len(self._columns) == len(self._units)
      assert len(self._columns) == len(self._formatters)

  def path(self): return self._target_dir

  def begin(self):
    '''Creates the data directory, initial snapshot, etc.  Must be called
        before add_points(). The run_measurement() context manager
        calls this automatically.
    '''
    assert not hasattr(self, "_start_time"), "begin() must be called only once."

    if self._target_dir == None:
      self._target_dir = str(datetime.datetime.now()).replace(".", "_").replace(":", "-").replace(" ", "_")

    parent_dir, target = os.path.split(self._target_dir)

    target = Measurement._path_friendly_str(target)

    # Append a number to target dir name if the dir already exists
    i = 2
    self._target_dir = os.path.join(parent_dir, target)
    while os.path.exists(self._target_dir):
      self._target_dir = os.path.join(parent_dir, '%s_%d' % (target, i))
      i += 1

    self._check_for_manual_abort()

    os.makedirs(self._target_dir)

    self._write_readme()
    self._open_log_file()
    self._copy_jupyter_notebook()
    self.write_snapshot()

    self._dat_file = open(os.path.join(self._target_dir, 'tabular_data.dat'), 'w')

    self._start_time = datetime.datetime.now()

  def _write_tabular_data_header(self):
    """Write a header in tabular_data.dat.

       The format is to some extent compatible with the "legacy"
       QCoDeS format, but adds some more metadata.

       This is invoked automatically during the first call to
       add_points(), rather than during begin(), since we want to
       infer the column dtypes from the first added points.

    """
    header =  "#\n"
    header += f"# ondisk_format_version = {'.'.join(map(str, ondisk_format_version))}\n"
    header += f"# pdata_version = {pdata.__version__}\n"
    header += f"# jsondiff_version = {jsondiff.__version__}\n"
    header += f"# numpy_version = {np.__version__}\n"
    header += f"# python_version = {sys.version}\n"
    header += "# Measurement started at " + self._start_time.strftime("%Y-%m-%d %H:%M:%S.%f\n")
    header += "# Column dtypes: " + "\t".join(Measurement._dtype_to_str(dt)
                                              for dt in self._dtypes) + "\n"
    header += "#\n"
    header += "# " + "\t".join(Measurement._replace_disallowed_tabular_data_chars(f"{c} ({u})")
                               for c,u in zip(self._columns, self._units)) + "\n"
    header += "#\n"
    try:     self._dat_file.write(header)
    finally: self._dat_file.flush()

  def end(self):
    '''Ends the measurement. Adds final metadata and closes and compresses
       the data set files. The run_measurement() context manager calls
       this automatically.
    '''
    if self._npoints_total == 0: self._write_tabular_data_header()

    footer =  "#\n"
    footer += "# Measurement ended at " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f\n")
    footer += f"# Snapshot diffs preceding rows (0-based index): {','.join(map(str, self._snapshot_diff_rows))}\n"
    try:     self._dat_file.write(footer)
    finally: self._dat_file.flush()

    self._close_dat_file()
    self._close_log_file()

  def add_points(self, data, snap=None):
    '''Add rows to the data table.

        The values for the columns are given
        as a dicitonary of the form::

            { 'column name 1': <array of values>,
              'column name 2': ... }.

       snap=True/False can override the "autosnap" option
       specified in __init__.
    '''

    for k in data.keys(): assert k in self._columns, '"%s" is not a column in the data table.' % k

    for k in self._columns: assert k in data.keys(), f'data must contain "{k}" as a key.'

    npts = len(data[self._columns[0]])
    assert all(len(data[k]) == npts for k in data.keys()), 'All appended data columns must be vectors of the same length.'

    if self._npoints_total == 0 and npts>0:
      self._guess_missing_formatters(data)
      self._write_tabular_data_header()

    if snap or (snap == None and self._autosnap): self.write_snapshot()

    # Prepare in memory
    rows = "\n".join(
      "\t".join(Measurement._replace_disallowed_tabular_data_chars(f(data[c][i]))
                for c,f in zip(self._columns, self._formatters))
      for i in range(npts) )
    rows += "\n"

    # And write to disk as atomically as possible
    try:     self._dat_file.write(rows)
    finally: self._dat_file.flush()

    self._npoints_total += npts

    self._check_for_manual_abort()

  def add_point(self, data, snap=None):
    ''' Same as add_points but takes scalar inputs for the column values. '''
    for k in data.keys(): assert np.isscalar(data[k]), f'data[{k}] seems to contain more than one value ({data[k]}). Did you mean to call add_point*s* instead?'
    self.add_points(dict( (k, [ data[k] ]) for k in data.keys() ),
                    snap=snap)

  def write_snapshot(self, snap=None):
    '''Add a snapshot (delta) file to the data directory. This is called
       automatically whenever you call add_points(), unless you
       disabled autosnapping.
    '''
    if snap==None:
      snap = self._get_snapshot()

    if self._last_snapshot == None:
      with open(os.path.join(self._target_dir, 'snapshot.json'), 'w') as fsnap:
        Measurement._dump_json(snap, fsnap)

      # Filter _after_ writing initial snapshot.
      if self._snap_diff_filter != None: snap = self._snap_diff_filter(snap)

    else:

      if self._snap_diff_filter != None: snap = self._snap_diff_filter(snap)
      d = jsondiff.diff(self._last_snapshot, snap, cls=PdataJSONDiffer, marshal=True)

      if len(d.keys()) == 0: return

      i = 0
      while True:
        fname = os.path.join(self._target_dir,
                             'snapshot.row-%u.diff%u.json' % (self._npoints_total, i))
        if not os.path.exists(fname): break

      self._snapshot_diff_rows.append(self._npoints_total)
      with open(fname, 'w') as fsnap: Measurement._dump_json(d, fsnap)

    self._last_snapshot = snap

  def _guess_missing_formatters(self, data):
    '''Given the first points added to the data file, assign reasonable
       formatters for columns that didn't have one manually specified.

       Also record original data type of each column.
    '''
    for i,c in enumerate(self._columns):
      if self._dtypes[i] == None:
        self._dtypes[i] = type(data[c][0])

      if self._formatters[i] == None:
        # Infer appropriate formatter
        if isinstance(data[c][0], float):
          self._formatters[i] = lambda x: f"{x:.15e}"
        elif isinstance(data[c][0], complex):
          self._formatters[i] = lambda x: f"{x.real:.15e}{x.imag:+.15e}j"
        elif isinstance(data[c][0], datetime.datetime):
          self._formatters[i] = lambda x: x.strftime('%Y-%m-%d %H:%M:%S.%f')
        else:
          self._formatters[i] = str

  def _open_log_file(self):
    ''' Open a secondary log file in the data directory. '''
    fn = os.path.join(self._target_dir, 'log.txt')
    if len(logging.getLogger().handlers) > 0:
      formatter = logging.getLogger().handlers[0].formatter
    else:
      formatter = None

    self._log_file_handler = logging.FileHandler(fn)
    self._log_file_handler.setLevel(logging.getLogger().level if self._log_level=="inherit" else self._log_level)
    self._log_file_handler.setFormatter(formatter)

    logging.getLogger().addHandler(self._log_file_handler)
    logging.debug('Added log_file_handler. path="%s", formatter="%s"' % (fn, str(formatter)))

  def _close_dat_file(self):
    self._dat_file.close()

    if self._compress:

      def gzip_file(fname):
        with open(fname, 'rb') as f_in:
          with gzip.open(fname + '.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(fname) # Remove original

      def tar_files(data_files, tar_name):
        with tarfile.open(os.path.join(self._target_dir, tar_name + '.tar.gz'),
                          'w:gz') as tar:
          for f in data_files:
            tar.add(f, arcname=os.path.split(f)[-1])
        for f in data_files: os.remove(f) # Remove originals

      # Compress tabular_data.dat
      gzip_file( os.path.join(self._target_dir, 'tabular_data.dat') )

      # Compress snapshot.json
      gzip_file( os.path.join(self._target_dir, 'snapshot.json') )

      # Add snapshot diffs to a compressed tar file.
      tar_files([ os.path.join(self._target_dir, f)
                  for f in os.listdir(self._target_dir)
                  if f.startswith('snapshot.row-') ],
                'snapshot_diffs')


  def _close_log_file(self):
    logging.getLogger().removeHandler(self._log_file_handler)
    self._log_file_handler.close()
    self._log_file_handler = None

  def _copy_jupyter_notebook(self):
    ''' Saves the current notebook (if any) and copies it to the data directory. '''
    try:
      fname = pdata.jupyter_helpers.get_notebook_name()
      if fname == None: return # Not running within Jupyter

      pdata.jupyter_helpers.save_notebook()
      shutil.copyfile(fname, os.path.join(self._target_dir, os.path.split(fname)[1]))
    except:
      logging.exception(f"Failed to copy measurement Jupyter notebook to {self.path()}. Starting experiment anyway.")

  def _write_readme(self):
    '''
    Creates a README file the the data directory with a brief
    description of the data format.
    '''
    if self._omit_readme: return

    with open(os.path.join(self._target_dir, 'README'), 'w') as f:
      f.write('This data directory was created by the '
              'pdata.procedural_data module at\n'
              '%s.\n\n' % datetime.datetime.now())

      f.write('The docsctring of the main Measurement class '
              'describes the data format:\n\n')

      f.write(Measurement.__doc__)

  def _check_for_manual_abort(self):
    try:
      t = os.path.getmtime(abort_signal_file)
    except FileNotFoundError:
      t = None

    if not hasattr(self, '_abort_signal_initial_mtime'):
      self._abort_signal_initial_mtime = t
      return

    if t != self._abort_signal_initial_mtime: raise Exception('Measurement aborted manually.')

  @staticmethod
  def _dump_json(snap, fhandle):
    json.dump(snap, fhandle, sort_keys=False,
              indent=2, ensure_ascii=False, cls=NumpyJSONEncoder)

  @staticmethod
  def _path_friendly_str(s):
    def acceptable_char(x): return x.isalnum() or x in ['#', '-', '=']
    return "".join(x if acceptable_char(x) else '_' for x in s)

  @staticmethod
  def _replace_disallowed_tabular_data_chars(s): return s.replace("\t","    ").replace("\n", " ").replace("#", " ")

  @staticmethod
  def _dtype_to_str(dt):
    """Convert datatype dt to str."""
    return Measurement._replace_disallowed_tabular_data_chars(
      f"{dt.__module__}.{dt.__name__}" if hasattr(dt, "__module__") and hasattr(dt, "__name__") else str(dt) )


# A bit of a hack allowing controllably aborting a measurement
# from another process on the same machine.
abort_signal_file = os.path.join(tempfile.gettempdir(),
                                 'pdata.abort-measurements.signal')
def abort_measurements():
  '''Abort all measurements running on this machine after their next
  call to add_points(), which is presumably a safe time to abort. Can
  be called from an independent process running on the same machine.
  '''
  with open(abort_signal_file, 'w') as f:
    f.write('Manual abort called for at %s\n' % datetime.datetime.now())
