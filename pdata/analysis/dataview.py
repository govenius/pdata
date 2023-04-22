'''
Class for post-processing measurement data.
'''

from pdata._metadata import __version__

import os
import time
import numpy as np
import types
import re
import logging
import copy
import shutil
import gzip
import tarfile
import itertools
import json
import jsondiff
import datetime
import pytz
from dateutil import tz
from collections import OrderedDict

UNIX_EPOCH = datetime.datetime(1970, 1, 1, 0, 0, tzinfo = pytz.utc)

column_name_regex = r"[\w\d\s\-+%=/*&]+"
column_unit_regex = r"[\w\d\s\-+%=/*&]*"

class PDataSingle():
    ''' Class for reading in the contents of a single pdata data directory.
        Almost always passed on to DataView for actual analysis. '''

    def __init__(self, path, convert_timestamps=True, parse_comments=False):
      '''Parse data stored in the specified directory path.

         convert_timestamps --> Convert values that look like time
         stamps into seconds since Unix epoch.

         parse_comments --> Parse comments placed between data
         rows. In the current implementation, parsing the comments
         requires a separate pass through the data.
      '''
      self._path = path

      def parse_initial_snapshot():
        self._snapshots = []
        if os.path.exists(os.path.join(path, 'snapshot.json')):
          with open(os.path.join(path, 'snapshot.json'), 'r') as f:
            self._snapshots.append((0, json.load(f)))
        else:
          with gzip.open(os.path.join(path, 'snapshot.json.gz'), 'r') as f:
            self._snapshots.append((0, json.load(f)))

      def add_snapshot_diff(row, f):
        # Deep copy the last snapshot -> VERY inefficient but easy & safe
        snap = json.loads(json.dumps(self._snapshots[-1][-1]))
        # Add the new copy with the changes
        self._snapshots.append((row, jsondiff.patch(snap, json.load(f), marshal=True)))

      def parse_snapshot_diff_names(fnames):
        """ Given a list of filenames, filter and sort the snapshot diffs. """
        diff_names = []

        for f in fnames:
          m = re.match(r'snapshot\.row-(\d+)\.diff(\d+)\.json', f)
          if m != None:
            diff_names.append((int(m.group(1)), int(m.group(2)), m.group(0)))
            continue
        diff_names.sort(key=lambda x: x[1]) # secondary sort on .diff<n>
        diff_names.sort(key=lambda x: x[0]) # primary sort on .row-<n>
        return diff_names

      def parse_tabular_data(f):
        # First extract the first data row and the header rows preceding it.
        header = PDataSingle._extract_header(f, parse_all_comments=parse_comments)
        self._comments = header["comments"]

        #print("\n" + header["table_header"])
        #if "first_data_row" in header.keys(): print(header["first_data_row"])
        #time.sleep(0.1)

        # Now parse the stored header
        if not "table_header" in header.keys():
          logging.warning(f"No header found in tabular data of {self._path}")
          self._column_names, self._units, dtypes = [], [], []
        else:
          self._column_names, self._units = PDataSingle._parse_columns_from_header(header["table_header"])
          dtypes, converters = PDataSingle._parse_dtypes_from_header(header["table_header"],
                                                                                 convert_timestamps=convert_timestamps)

        self._column_name_to_index = dict( (n, i) for i,n in enumerate(self._column_names) )

        if "first_data_row" in header.keys():
          # Analyze first data row
          inferred_dtypes, inferred_converters = PDataSingle._infer_dtypes_from_first_data_row(
              header["first_data_row"],
              convert_timestamps=(dtypes==None and convert_timestamps))
        else:
          inferred_dtypes, inferred_converters = dict( (i, float) for i in range(len(self._column_names)) ), {}

        assert len(self._column_names) == len(inferred_dtypes.keys()), "The number of columns in the header and first data row do not match."
        if dtypes is None:
          dtypes = inferred_dtypes
          converters = inferred_converters

        assert len(self._column_names) == len(dtypes.keys()), "The number of columns in the header and number of parsed dtypes do not match."
        dtypes = list( dtypes[i] for i in range(len(dtypes.keys())) )

        if "first_data_row" in header.keys():
          # Parse the actual numerical data.
          #
          # Use "col{i}" as names, rather than self._column_names,
          # since pdata column names may contain characters not
          # allowed in numpy structured arrays.
          f.seek(0)
          self._data = np.genfromtxt(f,
                                     delimiter="\t",
                                     comments="#",
                                     converters=dict( (f"col{i}", c) for i,c in converters.items() ),
                                     dtype=dtypes,
                                     names=list(f"col{i}" for i in range(len(self._column_names))) )

          # If the data contains just a single row, genfromtxt returns a 0D array! Fortunately reshaping still works.
          # Note: In Numpy >= 1.23.0, setting ndmin for genfromtxt might also solve this but that remains untested.
          try:
            len(self._data)
          except TypeError:
            self._data = self._data.reshape((-1,))

          # Parse the footer as well, if any
          self._footer = PDataSingle._parse_footer(PDataSingle._extract_footer(f))
          #print("\n\n"); print(footer); time.sleep(0.1)

        else:
          logging.warning(f"No data rows in tabular_data of {self._path}")
          self._data = np.array([], dtype=np.dtype(list( (f"col{i}", dt) for i,dt in enumerate(dtypes) )))
          self._footer = {}

        #print("\n" + repr(self._data)); time.sleep(0.1)

        if len(self._data) > 0:
          assert len(self._data[0]) == len(self._column_names), 'Unexcepted number of data columns: %s vs %s' % (len(self._data[0]), len(self._column_names))


      ###########################################################
      # Actually parse the data using the helper functions above
      ###########################################################

      # Parse main data file (possibly compressed)
      if os.path.exists(os.path.join(path, "tabular_data.dat")):
        with open(os.path.join(path, "tabular_data.dat"), 'r') as f:
          parse_tabular_data(f)

      elif os.path.exists(os.path.join(path, "tabular_data.dat.gz")):
        with gzip.open(os.path.join(path, "tabular_data.dat.gz"), 'rb') as f:
          parse_tabular_data(f)

      else:
        other_dat_files = [ pp for pp in os.scandir(path) if pp.name.endswith(".dat") ]
        if len(other_dat_files) == 0: assert False, f'No .dat file found in {os.path.abspath(path)}'
        logging.info(f"No tabular_data.dat(.gz) found in {path}. Using {other_dat_files[0].name} instead.")
        with open(other_dat_files[0].path, 'r') as f:
          parse_tabular_data(f)

      # Parse initial snapshot
      parse_initial_snapshot()

      # Parse snapshot diffs
      tar_fname = os.path.join(path, 'snapshot_diffs.tar.gz')
      if os.path.exists(tar_fname):
        with tarfile.open(tar_fname) as tar:
          for row,j,fname in parse_snapshot_diff_names(tar.getnames()):
            add_snapshot_diff(row, tar.extractfile(fname))

      else: # uncompressed snapshot diffs as separate files
        for row,j,fname in parse_snapshot_diff_names(os.listdir(path)):
          with open(os.path.join(path, fname)) as f:
            add_snapshot_diff(row, f)

      if "snapshot_diffs_preceding_rows" in self._footer.keys():
        # Check that snapshot diff rows parsed from file names match the info in the footer
        assert all( i==j for i,j in zip(self._footer["snapshot_diffs_preceding_rows"],
                                        [ r for r,s in self._snapshots[1:] ] )
                   ), "Snapshot diff rows parsed from file names don't match rows listed in tabular data footer."


    def name(self): return os.path.split(self._path)[-1]
    def filename(self): return self._path
    def dimension_names(self): return self._column_names
    def dimension_units(self): return self._units
    def npoints(self): return len(self._data)
    def data(self): return self._data

    def comments(self):
      return self._comments

    def settings(self):
      return self._snapshots

    def __getitem__(self, key):
      return self._data[f"col{self._column_name_to_index[key]}"]

    @staticmethod
    def _parse_timestamp(s):
      t = datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')
      return (t.astimezone() - UNIX_EPOCH).total_seconds()

    @staticmethod
    def _extract_header(f, parse_all_comments=False):
      """ Extract header and first data row from tabular data file f. """
      r = {} # Dict for results to return
      r["comments"] = []
      rowno = 0
      comment = ""
      while True:
        line = f.readline()
        if not isinstance(line, str): line = line.decode('utf-8')
        if len(line) == 0: break # EOF

        line = line.strip()
        if len(line) == 0: continue # empty line

        if line.startswith('#'): # comment line
          comment += line[1:].strip() + '\n'
          continue

        # Otherwise this is a data row
        comment = comment.strip()
        if len(comment) > 0:
          # Store comment(s) preceding this data row
          r["comments"].append((rowno, comment))

        # The comment rows preceding the first data row contain the
        # table header that defines the column names. Store the
        # header and the first data row for later parsing.
        if rowno==0:
          r["table_header"] = comment
          r["first_data_row"] = line

        rowno += 1
        comment = ""

        # Done parsing the header. We can stop here if not requested
        # to parse all comments, also after first data row.
        if not parse_all_comments: break

      # Store header even if there were zero data rows
      if rowno==0:
        # Header is in the "comment" variable at this point. But
        # "comment" may also contant a footer so strip everything
        # after "Measurement ended at".
        table_header = []
        for line in comment.split("\n"):
          if line.strip().startswith("Measurement ended at "): break
          table_header.append(line)
        r["table_header"] = "\n".join(table_header)

      return r

    @staticmethod
    def _infer_dtypes_from_first_data_row(line, convert_timestamps):
      """Infer data types from the first data row (in case the information
         is not available in the table header).
      """
      converters = {}
      dtypes = {}
      for i,c in enumerate(line.split('\t')):
        c = c.strip().lower()

        if c in ["true", "false"]:
          dtypes[i] = bool
          continue

        if convert_timestamps:
          # If col is a time stamp, convert it into seconds since Unix epoch.
          try:
            PDataSingle._parse_timestamp(c)
            converters[i] = lambda x: PDataSingle._parse_timestamp(x.decode('utf-8'))
            dtypes[i] = float
            logging.info(f'Column {i} appears to contain timestamps. Converting them to seconds since Unix epoch. (Disable by setting convert_timestamps=False.)')
            continue
          except ValueError:
            pass # Not a timestamp

        try:
          # Convert all numerical types to float, including
          # integers. This is a bit safer, in case the first row looks
          # like an int but other rows contain floats.
          float(c)
          dtypes[i] = float
          continue
        except ValueError:
          pass # Not a float, int, or similar number

        # Otherwise parse this column as str
        dtypes[i] = str

      return dtypes, converters

    @staticmethod
    def _parse_dtypes_from_header(s, convert_timestamps):
      """Check for dtype specification in the
         "Column dtypes: float\tfloat\tint\t..." format. """
      m = re.search(r'(?m)^\s*Column dtypes:\s*(.*?)?$', s)
      if m==None or len(m.groups()) != 1: return None, None

      dtypes = {}
      converters = {}
      for i,dt in enumerate(m.group(1).split("\t")):
        dt = dt.strip()
        if dt.startswith("numpy."):
          try:
            dtypes[i] = getattr(np, dt[len("numpy."):])
          except AttributeError:
            logging.warning(f"Column {i} dtype = {dt} seems like a numpy data type based on prefix, "
                            f"but numpy.{dt} doesn't exist. Falling back to str.")
            dtypes[i] = str
        elif dt.startswith("builtins."):
          dtypes[i] = eval(dt[len("builtins."):])
        elif dt in ["datetime.datetime", "datetime"]:
          if convert_timestamps:
            dtypes[i] = float
            converters[i] = lambda x: PDataSingle._parse_timestamp(x.decode('utf-8'))
          else:
            logging.info(f'Column {i} contains timestamps. Converting them to seconds since Unix epoch. (Disable by setting convert_timestamps=False.)')
            dtypes[i] = datetime.datetime
            converters[i] = lambda x: dtypes[i](x.decode('utf-8'))
        else:
          if not dt in [ "None" ]:
            logging.warning(f"Column {i} dtype = {dt} unrecognized. Falling back to str.")
          dtypes[i] = str

      return dtypes, converters

    @staticmethod
    def _parse_columns_from_header(s):
      """Parse column names and units from table header. Asssume that the
         last non-empty header line has them in the "Column name
         (unit)\t" format. If not, fall back to assuming similar but
         simpler legacy QCoDeS format.
      """
      # Split into lines and keep only non-empty ones
      column_names_and_units = [ l for l in s.split('\n') if len(l.strip())>0 ]
      if len(column_names_and_units) == 0: return [],[]

      try:
        cols = []
        units = []
        for c in column_names_and_units[-1].split('\t'):
          m = re.match(f'({column_name_regex})\s+\(({column_unit_regex})\)', c.strip())
          cols.append(m.group(1))
          units.append(m.group(2))

      except AttributeError:
        # Try assuming the legacy format used in QCoDeS (qcodes/data/gnuplot_format.py)
        try:
          # Last row contains the number of data points --> ignore
          if column_names_and_units[-1].strip().isdigit(): del column_names_and_units[-1]

          cols = [ c.strip().strip('"') for c in column_names_and_units[-1].split('\t') ]
          units = [ '' for i in range(len(cols))]
        except IndexError:
          logging.warning(f"Could not parse tabular data header. Header: {s}")
          raise

      return cols, units

    @staticmethod
    def _extract_footer(f, chunk_size=4096):
      """Return tabular data footer from file object f. The footer contains,
         by defition, all rows following the last data row (= last
         non-empty row not starting with #).

         Assumes that current position is already at the end of the
         file.

         If there are zero data rows, the parsed string may also
         include the header.

      """

      b = isinstance(f.read(0), bytes) # Check whether we read bytes or strings from f

      tail = b"" if b else ""
      while True:
        try:
          # Append one more chunk to tail
          f.seek(-min(f.tell(), (1 + (len(tail)>0))*chunk_size), os.SEEK_CUR)
          tail = f.read(chunk_size) + tail
        except IOError:
          # Read entire file into tail
          logging.debug(f"Could not read footer in chunks from end of file object {f} --> Reading entire file.")
          f.seek(0)
          tail = f.read()
          break

        # Check whether tail already contains non-comment rows.
        # If so, we must have read the entire footer already
        if any( not (l.strip().startswith(b"#" if b else "#") or len(l.strip())==0)
                for l in tail.split(b"\n" if b else "\n") ):
          break

      # Remove non-comment rows:
      footer = []
      for l in reversed(tail.split(b"\n" if b else "\n")):
        l = l.strip()
        if len(l)==0: continue
        if b: l = l.decode("utf-8")
        if not l.startswith("#"): break
        footer.append(l[1:].strip())

      return "\n".join(reversed(footer))

    @staticmethod
    def _parse_footer(raw_footer):

      r = { "raw_footer": raw_footer }

      # Parse information from standard rows in the footer.
      m = re.search(r'(?m)^\s*Snapshot diffs preceding rows \(0-based index\):\s*(.*?)?$', raw_footer)
      if m!=None and len(m.groups()) == 1:
        try:
          r["snapshot_diffs_preceding_rows"] = np.array([ int(i) for i in m.group(1).split(",") ]
                                                        if m.group(1).strip() != "" else [],
                                                        dtype=int)
        except:
          logging.exception(f"Failed to parse snapshot diff row spec '{m.group(1)}' into a list of ints.")

      m = re.search(r'(?m)^\s*Measurement ended at\s+(.*?)?$', raw_footer)
      if m!=None and len(m.groups()) == 1:
        try:
          r["measurement_ended_at"] = datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S.%f')
        except:
          logging.exception(f"Failed to parse measurement end time '{m.group(1)}' into a datetime object.")

      return r


class DataView():
    '''
    Class for post-processing measurement data. Main features are:
      * Concatenating multiple separate data objects
      * Creating "virtual" columns by parsing comments or snapshot files
        or by applying arbitrary functions to the data
      * Dividing the rows into "sweeps" based on various criteria.

    See docs/examples/Procedural Data and DataView.ipynb for example use.
    '''

    def __init__(self, data, deep_copy=False, source_column_name='data_source'):
        '''
        Create a new view of existing data objects for post-processing.
        The original data objects will not be modified.

        args:
          data -- Data object(s). Each data object needs to provide the following methods:
                     * name()     # Arbitrary string identifier for the data object
                     * filename() # Specifies the path to the main datafile
                                      # (for identification/debugging purpose only)
                     * dimension_names() # List of all data column names
                     * dimension_units() # List of all data column units
                     * npoints()  # Number of data points/rows.
                     * data()     # 2D ndarray containing all data rows and columns.
                     * comments()  # List of tuples (data_row_no, comment string),
                                      #   where data_row_no indicated the index of
                                      #   the data point that the comment precedes.
                     * settings()  # List of tuples (data_row_no, settings dict),
                                      #   where data_row_no indicated the index of
                                      #   the data point that the settings apply to.

        kwargs input:
          deep_copy          -- specifies whether the underlying data is copied or 
                                only referenced (more error prone, but memory efficient)
          source_column_name -- specifies the name of the (virtual) column that tells which
                                data object the row originates from. Specify None, if
                                you don't want this column to be added.
        '''

        self._virtual_dims = {}

        if isinstance(data, DataView): # clone
          # these private variables should be immutable so no need to deep copy
          self._dimensions = data._dimensions
          self._units = data._units
          self._source_col = data._source_col
          self._comments = data._comments
          self._settings = data._settings
          
          if deep_copy:
            self._data = data._data.copy()
          else:
            self._data = data._data

          # Always deep copy the mask
          self._mask = data._mask.copy()

          for name, fn in data._virtual_dims.items():
              self._virtual_dims[name] = fn

          return

        def get_source_column_name(dat):
          return f"{dat.name()}_({dat.filename().strip('.dat')})"

        def is_pdatasingle_like(x):
          return ( hasattr(x, "dimension_names") and hasattr(x, "dimension_units")
                   and hasattr(x, "name") and hasattr(x, "comments")
                   and hasattr(x, "data") )

        if is_pdatasingle_like(data): # data is a single Data object
          self._dimensions = data.dimension_names()
          self._units = dict(zip(data.dimension_names(), data.dimension_units()))
          unmasked = dict( (dim, data[dim]) for dim in data.dimension_names() )

          if source_column_name != None:
            n = get_source_column_name(data)
            self._source_col = [n for i in range(data.npoints())]
          else:
            self._source_col = None

          self._comments = data.comments()

          try:
            self._settings = data.settings()
          except:
            logging.exception("Could not parse the instrument settings file. Doesn't matter if you were not planning to add virtual columns based on values in the snapshot files.")
            self._settings = None

        else: # probably data is a sequence of Data objects then
          assert all(is_pdatasingle_like(dd) for dd in data), "data does not seem to be a PDataSingle-like object, nor a sequence of them: " + repr(data)

          self._dimensions = set(itertools.chain( *(dd.dimension_names() for dd in data) ))

          unmasked = {}
          for dim in self._dimensions:
            unmasked[dim] = []
            for dat in data:
              if len(dat.dimension_names()) == 0:
                logging.warning("%s seems to contain zero columns. Skipping it..." % (dat.filename()))
                continue

              n_rows = dat.npoints()
              if n_rows == 0:
                logging.info("%s seems to contain zero rows. Skipping it..." % (dat.filename()))
                continue

              try:
                unmasked[dim].append(dat[dim])
              except KeyError:
                logging.warning(f"Dimension {dim} does not exist in data object {str(dat)}. Omitting the dimension.")
                del unmasked[dim]
                break

            # concatenate rows from all files
            if dim in unmasked.keys():
              unmasked[dim] = np.concatenate(unmasked[dim]) if len(unmasked[dim])>0 else np.array([])

          # add a column that specifies the source data file
          lens = [ dat.npoints() for dat in data ]
          if source_column_name != None:
            names = [ get_source_column_name(dat) for dat in data ]
            self._source_col = [ [n for jj in range(l)] for n,l in zip(names,lens) ]
            #self._source_col = [ jj for jj in itertools.chain.from_iterable(self._source_col) ] # flatten
            self._source_col = list(itertools.chain.from_iterable(self._source_col)) # flatten
          else:
            self._source_col = None

          # keep only dimensions that could be parsed from all files
          self._dimensions = unmasked.keys()

          # take units from first data set
          self._units = dict(zip(data[0].dimension_names(), data[0].dimension_units()))

          # concatenate comments, adjusting row numbers from Data object rows to the corresponding dataview rows
          lens = np.array(lens)

          self._comments = [ dat.comments() for dat in data ]
          all_comments = []
          for jj,comments in enumerate(self._comments):
              all_comments.append([ (rowno + lens[:jj].sum(), commentstr) for rowno,commentstr in comments ])
          self._comments = list(itertools.chain.from_iterable(all_comments)) # flatten by one level

          # concatenate settings (snapshot) files in the same way
          self._settings = [ dat.settings() for dat in data ]
          all_settings = []
          for jj,settings in enumerate(self._settings):
              all_settings.append([ (rowno + lens[:jj].sum(), sett) for rowno,sett in settings ])
          self._settings = list(itertools.chain.from_iterable(all_settings)) # flatten by one level

        # Check for existence of multiple settings dicts for a single
        # data row. If they exist, we only care about the last one. --> Remove others.
        for i in range(len(self._settings)-1,0,-1):
          if self._settings[i][0] == self._settings[i-1][0]: del self._settings[i-1]

        # Initialize masks
        self._data = unmasked
        self._mask = np.zeros(0 if len(unmasked.keys())==0 else
                              len(unmasked[list(unmasked.keys())[0]]), dtype=bool)
        self._mask_stack = []

        self.set_mask(False)

        if source_column_name != None:
          self.add_virtual_dimension(source_column_name, arr=np.array(self._source_col))

    def __getitem__(self, index):
        '''
        Get the values of a given dimension as a vector.
        '''
        assert isinstance(index, str), "Data must be indexed using a dimension name. Dimensions in this Dataview: {self.dimensions()}"
        return self.column(index)

    def copy(self, copy_data=False):
        '''
        Make a copy of the view. The returned copy will always have an independent mask.
        
        copy_data -- whether the underlying data is also deep copied.
        '''
        return DataView(self, deep_copy=copy_data)

    def data_source(self):
        '''
        Returns a list of strings that tell which Data object each of the unmasked rows originated from.
        '''
        return [ i for i in itertools.compress(self._source_col, ~(self._mask)) ]

    def clear_mask(self):
        '''
        Unmask all data (i.e. make all data in the initially
        provided Data object visible again).
        '''
        self._mask[:] = False
        self._mask_stack = []

    def mask(self):
        '''
        Get a vector of booleans indicating which rows are masked.
        '''
        return self._mask.copy()

    def dimensions(self):
        '''
        Returns a list of all dimensions, both real and virtual.
        '''
        return list(itertools.chain(self._data.keys(), self._virtual_dims.keys()))

    def units(self, d):
        '''
        Returns the units for dimension d
        '''
        return self._units[d]

    def comments(self):
        '''
        Return the comments parsed from the data files.

        Returns tuples where the first item is an index to the
        first datarow that the comment applies to.
        '''
        return self._comments

    def settings(self):
        '''
        Return the settings parsed from the settings files.

        Returns tuples where the first item is an index to the
        first datarow that the settings apply to.
        '''
        return self._settings

    def continuous_ranges(self, masked_ranges=False):
        '''
        Returns a list of (start,stop) tuples that indicate continuous ranges of (un)masked data.
        '''
        m = self.mask() * (-1 if masked_ranges else 1)
        
        dm = m[1:] - m[:-1]
        starts = 1+np.where(dm < 0)[0]
        stops = 1+np.where(dm > 0)[0]

        if not m[0]:
            starts = np.concatenate(( [0], starts ))
        if not m[-1]:
            stops = np.concatenate(( stops, [len(m)] ))

        return zip(starts, stops)

    def set_mask(self, mask):
        '''
        Set an arbitrary mask for the data. Should be a vector of booleans of
        the same length as the number of data points.
        Alternatively, simply True/False masks/unmasks all data.

        See also mask_rows().
        '''
        try:
          if mask:
            self._mask[:] = True
          else:
            self._mask[:] = False
        except:
          m = np.zeros(len(self._mask), dtype=bool)
          m[mask] = True
          self._mask = m

    def mask_rows(self, row_mask, unmask_instead = False):
        '''
        Mask rows in the data. row_mask can be a slice or a boolean vector with
        length equal to the number of previously unmasked rows.

        The old mask is determined from the mask of the first column.

        Example:
          d = DataView(...)
          # ignore points where source current exceeds 1 uA.
          d.mask_rows(np.abs(d['I_source']) > 1e-6)
        '''
        old_mask = self._mask
        n = (~old_mask).astype(int).sum() # no. of previously unmasked entries
        #logging.debug("previously unmasked rows = %d" % n)

        # new mask for the previously unmasked rows
        new_mask = np.empty(n, dtype=bool); new_mask[:] = unmask_instead
        new_mask[row_mask] = (not unmask_instead)
        #logging.debug("new_mask.sum() = %d" % new_mask.sum())

        # combine the old and new masks
        full_mask = old_mask.copy()
        full_mask[~old_mask] = new_mask

        logging.debug("# of masked/unmasked rows = %d/%d" % (full_mask.astype(int).sum(), (~full_mask).astype(int).sum()))
        self.set_mask(full_mask)

    def push_mask(self, mask, unmask_instead = False):
        '''
        Same as mask_rows(), but also pushes the mask to a 'mask stack'.
        Handy for temporary masks e.g. inside loops.
        See also pop_mask().
        '''
        self._mask_stack.append(self.mask())
        self.mask_rows(mask, unmask_instead = unmask_instead)

    def pop_mask(self):
        '''
        Pop the topmost mask from the mask stack,
        set previous mask in the stack as current one
        and return the popped mask.
        Raises an exception if trying to pop an empty stack.
        '''
        try:
          previous_mask = self._mask_stack.pop()
        except IndexError as e:
          raise Exception("Trying to pop empty mask stack: %s" % e)

        self.set_mask(previous_mask)
        return previous_mask

    def remove_masked_rows_permanently(self):
        '''
        Removes the currently masked rows permanently.

        This is typically unnecessary, but may be useful
        before adding (cached) virtual columns to
        huge data sets where most rows are masked (because
        the cached virtual columns are computed for
        masked rows as well.)
        '''
        # Removing the real data rows themselves is easy.
        for d in self._data.keys():
          self._data[d] = self._data[d][~(self._mask)]

        # but we have to also adjust the comment & settings line numbers
        s = np.cumsum(self._mask.astype(int))
        def n_masked_before_line(lineno): return s[max(0, min(len(s)-1, lineno-1))]
        self._comments = [ (max(0,lineno-n_masked_before_line(lineno)), comment) for lineno,comment in self._comments ]
        self._settings = [ (max(0,lineno-n_masked_before_line(lineno)), setting) for lineno,setting in self._settings ]

        # as well as remove the masked rows from cached virtual columns.
        # However, _virtual_dims is assumed to be immutable in copy() so
        # we must copy it here!
        old_dims = self._virtual_dims
        self._virtual_dims = {}
        for name, dim in old_dims.items():
          cached_arr = dim['cached_array']
          if isinstance(cached_arr, np.ndarray):
            cached_arr = cached_arr[~(self._mask)]
          elif cached_arr != None:
            cached_arr = [ val for i,val in enumerate(cached_arr) if not self._mask[i] ]
          self._virtual_dims[name] = { 'fn': dim['fn'], 'cached_array': cached_arr }

        # finally remove the obsolete mask(s)
        self._mask = np.zeros(len(self._data[list(self._data.keys())[0]]), dtype=bool)
        self._mask_stack = []

    def single_valued_parameter(self, param):
        ''' If all values in the (virtual) dimension "param" are the same, return that value. '''
        assert len(np.unique(self[param])) == 1 or (all(np.isnan(self[param])) and len(self[param]) > 0), \
            '%s is not single valued for the current unmasked rows: %s' % (param, np.unique(self[param]))
        return self[param][0]

    def all_single_valued_parameters(self):
        params = OrderedDict()
        for p in self.dimensions():
          try: params[p] = self.single_valued_parameter(p)
          except: pass
        return params

    def divide_into_sweeps(self, sweep_dimension, use_sweep_direction = None):
        '''Divide the rows into "sweeps" based on a monotonously increasing
        or decreasing value of column "sweep_dimension", if use_sweep_direction==True.

        If use_sweep_direction==False, sequences of points where
        "sweep_dimension" stays constant are considered sweeps. This
        is useful for splitting the data into sweeps based on a slowly
        varying parameter, e.g. a gate voltage set point that is
        changed between IV curve sweeps.

        If use_sweep_direction is None, this function tries to figure
        out which one is more reasonable.

        Returns a sequence of slices indicating the start and end of
        each sweep.

        Note that the indices are relative to the currently _unmasked_
        rows only.

        '''
        sdim = self[sweep_dimension]

        if isinstance(sdim[0], str):
          use_sweep_direction = False
          dx = np.array([ sdim[i+1] != sdim[i] for i in range(len(sdim)-1) ])
        else:
          dx = np.sign(sdim[1:] - sdim[:-1])

        if use_sweep_direction == None:
          use_sweep_direction = ( np.abs(dx).astype(int).sum() > len(dx)/4. )

        if use_sweep_direction:
          logging.info("Assuming '%s' is swept." % sweep_dimension)
        else:
          logging.info("Assuming '%s' stays constant within a sweep." % sweep_dimension)

        if use_sweep_direction:
          for i in range(1,len(dx)):
              if i+1 < len(dx) and dx[i] == 0: dx[i]=dx[i+1] # this is necessary to detect changes in direction, when the end point is repeated
          change_in_sign = (2 + np.array(np.where(dx[1:] * dx[:-1] < 0),dtype=int).reshape((-1))).tolist()

          # the direction changing twice in a row means that sweeps are being done repeatedly
          # in the same direction.
          for i in range(len(change_in_sign)-1, 0, -1):
            if change_in_sign[i]-change_in_sign[i-1] == 1: del change_in_sign[i]

          if len(change_in_sign) == 0: return [ slice(0, len(sdim)) ]

          start_indices = np.concatenate(([0], change_in_sign))
          stop_indices  = np.concatenate((change_in_sign, [len(sdim)]))

          sweeps = np.concatenate((start_indices, stop_indices)).reshape((2,-1)).T
        else:
          change_in_sdim = 1 + np.array(np.where(dx != 0)).reshape((-1))
          if len(change_in_sdim) == 0: return [ slice(0, len(sdim)) ]

          start_indices = np.concatenate(([0], change_in_sdim))
          stop_indices  = np.concatenate((change_in_sdim, [len(sdim)]))
        
          sweeps = np.concatenate((start_indices, stop_indices)).reshape((2,-1)).T

        return [ slice(max(s, 0), min(e, len(sdim))) for s,e in sweeps ]

    def mask_sweeps(self, sweep_dimension, sl, unmask_instead=False):
        '''
        Mask entire sweeps (see divide_into_sweeps()).

        sl can be a single integer or any slice object compatible with a 1D numpy.ndarray (list of sweeps).

        unmask_instead -- unmask the specified sweeps instead, mask everything else
        '''
        sweeps = self.divide_into_sweeps(sweep_dimension)
        row_mask = np.zeros(len(self[sweep_dimension]), dtype=bool)
        for start,stop in ([sweeps[sl]] if isinstance(sl, int) else sweeps[sl]):
            logging.debug("%smasking start: %d, stop %d" % ('un' if unmask_instead else '',start, stop))
            row_mask[start:stop] = True
        self.mask_rows(~row_mask if unmask_instead else row_mask)


    def unmask_sweeps(self, sweep_dimension, sl):
        '''
        Mask all rows except the specified sweeps (see divide_into_sweeps()).

        sl can be a single integer or any slice object compatible with a 1D numpy.ndarray (list of sweeps).
        '''
        self.mask_sweeps(sweep_dimension, sl, unmask_instead=True)

    def column(self, name, deep_copy=False):
        '''
        Get the non-masked entries of dimension 'name' as a 1D ndarray.
        name is the dimension name.

        kwargs:
          deep_copy -- copy the returned data so that it is safe to modify it.
        '''
        if name in self._virtual_dims.keys():
            d = self._virtual_dims[name]['cached_array']
            if d is None: d = self._virtual_dims[name]['fn'](self)
            if len(d) == len(self._mask): # The function may return masked or unmasked data...
              # The function returned unmasked data so apply the mask
              try:
                d = d[~(self._mask)] # This works for ndarrays
              except:
                # workaround to mask native python arrays
                d = [ x for i,x in enumerate(d) if not self._mask[i] ]
            return d
        else:
            d = self._data[name][~(self._mask)]

        if deep_copy: d = d.copy()
        return d

    non_numpy_array_warning_given = []
    def add_virtual_dimension(self, name, units="", fn=None, arr=None, comment_regex=None, from_set=None, dtype=float, preparser=None, cache_fn_values=True, return_result=False):
        '''
        Makes a computed vector accessible as self[name].
        The computed vector depends on whether fn, arr or comment_regex is specified.

        It is advisable that the computed vector is of the same length as
        the real data columns.
        
        kwargs:

          Arguments for specifying how to parse the value:

          fn            -- the function applied to the DataView object, i.e self[name] returns fn(self)
          arr           -- specify the column directly as an array, i.e. self[name] returns arr
          comment_regex -- for each row, take the value from the last match in a comment, otherwise np.NaN. Should be a regex string.
          from_set      -- for each row, take the value from the corresponding snapshot file. Specify as a tuple that indexes the settings dict ("instrument_name", "parameter_name", ...).

          Other options:

          dtype           -- data type (default: float)
          preparser       -- optional preparser function that massages the value before it is passed to dtype
          cache_fn_values -- evaluate fn(self) immediately for the entire (unmasked) array and cache the result
          return_result   -- return the result directly as an (nd)array instead of adding it as a virtual dimension
        '''
        logging.debug('adding virtual dimension "%s"' % name)

        assert (fn != None) + (arr is not None) + (comment_regex != None) + (from_set != None) == 1, 'You must specify exactly one of "fn", "arr", or "comment_regex".'

        if arr is not None:
          assert len(arr) == len(self._mask), f'len(arr)={len(arr)} must be the same as the length of the existing data columns ({len(self._mask)}).'

        if from_set != None:
            assert self._settings != None, 'snapshot files were not successfully parsed during dataview initialization.'

        if comment_regex != None or from_set != None:
            # construct the column by parsing the comments or snapshots
            use_set = (from_set != None) # shorthand for convenience

            # pre-allocate an array for the values
            try:
              if issubclass(dtype, str):
                raise Exception('Do not store strings in numpy arrays (because it "works" but the behavior is unintuitive, i.e. only the first character is stored if you just specify dtype=str).')
              vals = np.zeros(len(self._mask), dtype=dtype)
              if dtype == float: vals += np.nan # initialize to NaN instead of zeros
            except:
              if not name in self.non_numpy_array_warning_given:
                logging.info("%s does not seem to be a numpy data type. The virtual column '%s' will be a native python array instead, which may be slow." % (str(dtype), name))
                self.non_numpy_array_warning_given.append(name)
              vals = [None for jjj in range(len(self._mask))]

            def set_vals(up_to_row, new_val):
              """
              Helper that sets values up to the specified row, starting from where we last left off.

              This is a little trickier than might seem at first because when we parse a new value,
              we don't yet know the row up to which it applies. Instead, we always set the previous value
              up to row where the new value appeared (and remember the new value for the next call).
              """
              if up_to_row > set_vals.prev_match_on_row:

                # Apply preparser() and dtype(() to the previously parsed value.
                #
                # It's good to do it only here because occasionally there may be multiple definitions for the 
                # same column and same row, usually on row zero.
                # These might not all have valid syntax for preparser/dtype()
                # so it's best to only parse the one that matters (the last one).
                v = set_vals.prev_val
                try:
                  if preparser != None: v = preparser(v)
                  v = dtype(v)
                except:
                  #logging.exception('Could not convert the parsed value (%s) to the specifed data type (%s).'
                  #                  % (v, dtype))
                  raise

                if isinstance(vals, np.ndarray): vals[set_vals.prev_match_on_row:up_to_row] = v
                else: vals[set_vals.prev_match_on_row:up_to_row] = ( v for jjj in range(up_to_row-set_vals.prev_match_on_row) )
                logging.debug('Setting value for rows %d:%d = %s' % (set_vals.prev_match_on_row, up_to_row, v))

              set_vals.prev_match_on_row = up_to_row
              set_vals.prev_val = new_val

            set_vals.prev_match_on_row = 0

            #logging.debug(self._comments)

            for rowno,commentstr in (self._settings if use_set else self._comments):
              if use_set:
                # simply use the value from the snapshot file
                assert from_set[0] in commentstr.keys(), '"%s" not found in settings.' % from_set[0]
                new_val = commentstr
                for k in from_set: new_val = new_val[k]
              else:
                # see if the comment matches the specified regex
                m = re.search(comment_regex, commentstr)
                if m == None: continue
                #logging.debug('Match on row %d: "%s"' % (rowno, commentstr))

                if len(m.groups()) != 1:
                  logging.warning('Did not get a unique match (%s) in comment (%d): %s'
                               % (str(groups), rowno, commentstr))
                new_val = m.group(1)

              set_vals(up_to_row=rowno, new_val=new_val)

            logging.debug('Setting value for (remaining) rows %d: = %s' % (set_vals.prev_match_on_row, set_vals.prev_val))
            set_vals(up_to_row=len(vals), new_val=None)
            

            return self.add_virtual_dimension(name, units=units, arr=vals, return_result=return_result)

        if cache_fn_values and arr is None:
            old_mask = self.mask().copy() # backup the mask
            self.clear_mask()
            vals = fn(self)
            self.mask_rows(old_mask) # restore the mask

            return self.add_virtual_dimension(name, units=units, arr=vals, cache_fn_values=False, return_result=return_result)

        if return_result:
          return arr
        else:
          self._virtual_dims[name] = {'fn': fn, 'cached_array': arr}
          self._units[name] = units

    def remove_virtual_dimension(self, name):
        if name in self._virtual_dims.keys():
            del self._virtual_dims[name]
        else:
            logging.warning('Virtual dimension "%s" does not exist.' % name)

    def remove_virtual_dimensions(self):
        self._virtual_dims = {}

    def to_xarray(self, values, coords, fill_value=np.nan,
                  coarse_graining={}, include_single_valued_params=True):
        """Create an N-dimensional xarray DataSet out of values, where N is
           equal to the number of coordinates and values are specified
           as a list of dataview dimension names, or (<data variable
           name>, f, <units>) tuples where f(self) returns a vector of
           length equal to the number of unmasked rows in this
           DataView. Alternatively, values can be a single dimension
           name. Coordinates are specified as a list of dimension
           names. Entries of the xarray corresponding to coordinate
           combinations that don't exist in this data set are filled
           with fill_value.

           This is well-suited for N-dimensional parameter/coordinate
           sweeps that were executed with nested for loops in which
           the looped coordinate values in each loop were selected
           mostly independent of other coordinates. Otherwise there
           will be lots of fill_value's.

           Usually, you'll want to use setpoints, rather than measured
           values, as coordinates. If a coordinate c is instead a
           measured value, you probably want to specify coarse
           graining with coarse_graining={c: <Delta>}, which causes
           coordinates differing by at most <Delta> to be interpreted
           as the same coordinate.

           Note that if the same coordinate combination is repeated
           more than once in the data set, only the last measured
           value will appear in the output xarray. If you want to
           preserve information about repetitions, add another
           coordinate for the repetition number.

           If include_single_valued_params is True, all single valued
           parameters will be included as attributes of the xarray.

           Spaces, dashes and other special characters in coordinate
           names are replaced automatically by underscores, as these
           don't work well with xarray syntax.
        """
        # Get unique coordinate values for each coordinate
        coords = OrderedDict((c, np.unique(self[c])) for c in coords )

        # Mappings from unique coordinate values to coordinate index
        coord_to_i = dict( (c, dict( (cc,i) for i,cc in enumerate(coords[c]) ))
                           for c in coords.keys() )

        # Merge similar coordinates
        for c,delta in coarse_graining.items():
          coords[c] = list(coords[c]) # since ndarray elements cannot be deleted
          i = 1
          while i < len(coords[c]):
            if coords[c][i] - coords[c][i-1] <= delta:
              # Map the two coordinates to the same index
              coord_to_i[c][coords[c][i]] = coord_to_i[c][coords[c][i-1]]

              # Must also decrement all larger index mappings by one
              for cc in coord_to_i[c].keys():
                if cc > coords[c][i]: coord_to_i[c][cc] -= 1

              # Delete the nearly identical coordinate
              del coords[c][i]
            else:
              i +=1
          coords[c] = np.array(coords[c])

        # Special characters to underscores in coordinate names
        special_chars = r"[\s\-+%=/*&]"
        dims = list(coords.keys())
        for i,c in enumerate(dims):
          if re.search(special_chars, c) is not None:
            new_c = re.sub(special_chars, "_", c, count=len(c))
            assert new_c not in dims, f"{new_c} already exists in coords: {dims}"
            dims[i] = new_c

        # Create the xarrays

        # Also accept a single dimension name as input
        if isinstance(values, str): values = [ values ]

        import xarray
        arrays = OrderedDict()
        if include_single_valued_params: single_valued_params = self.all_single_valued_parameters()

        for value in values:
          if isinstance(value, str):
            val_name = value
            val_vector = self[value]
            units = self.units(value)
          else:
            val_name = value[0]
            val_vector = value[1](self)
            units = value[2]

          # Initialize all values as fill_value
          value_matrix = np.zeros(tuple(len(v) for v in coords.values()), dtype=val_vector.dtype) + fill_value

          # Copy values from self[value] to the correct index in the value_matrix.
          for i,v in enumerate(val_vector):
            value_matrix[tuple(coord_to_i[c][self[c][i]] for c in coords.keys())] = v

          # Attributes
          attrs = { "units": units,
                    "coord_units": dict((c, self.units(c)) for c in coords.keys()) }

          if include_single_valued_params:
            for p,v in single_valued_params.items(): attrs[p] = v

          arrays[val_name] = xarray.DataArray(value_matrix, coords=coords.values(), dims=dims, attrs=attrs)

        return xarray.Dataset(arrays)
