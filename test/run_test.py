
import logging
import os
import shutil
import tempfile
import time
import io
import datetime

import unittest

import numpy as np
import numpy.random

from pdata.procedural_data import run_measurement
from pdata.analysis.dataview import DataView, PDataSingle
from pdata.analysis import dataexplorer

def resonator_response(f, pwr, Qc=1e3, f0=6e9):
  """ Generate fake resonator S21 data, given a list of frequencies and a measurement power. """
  Qi = 0.5e3 * 2**(pwr/10.)
  Q = 1/(1/Qc + 1/Qi)
  return 1 - Q/Qc / (1 + 2j*Q*(f-f0)/f0)

alphabet = "abcdefghijklmnopqrstuvwxyz"

class TestSavingAndAnalysis(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    """ Create some fake data and save it on disk. """

    cls._data_root = tempfile.mkdtemp(prefix='pdata_test_')
    cls._typical_datadir = None

    freqs = np.linspace(5.9e9, 6.1e9, 41)

    def VNA_instrument():
      """ Fake VNA "instrument" that retuns a list of |S21| that depends on a power parameter. """
      return resonator_response(freqs, VNA_instrument._power)

    VNA_instrument._power = 10. # Initial value

    def get_instrument_snapshot():
      """ Fake snapshot of instrument parameters. """
      snap = {
        'instruments': {
          "VNA1": { "power": VNA_instrument._power, "RBW": 10e3,
                    "freqs": freqs,
                    "random_scalar": np.random.randn(),
                    "random_list": np.random.randn(10).tolist(),
                    "random_ndarray": np.random.randn(10)
                   },
          "voltage_source1": { "V": -1.234 },
          "voltage_source2": { "V": -5.678, "strange unicode characters": "∰ ᴥ ❽ ⁂" },
        },
        "list": [ "list_value0", {"key": "value"} ]}

      if get_instrument_snapshot.counter % 2 == 0: snap["key_that_gets_removed"] = "value_for_key_that_gets_removed"

      if get_instrument_snapshot.counter > 0: snap["key_that_gets_added"] = "value_for_key_that_gets_added"

      get_instrument_snapshot.counter += 1
      return snap

    get_instrument_snapshot.counter = 0

    # Create typical dataset
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21",
                                    "col with strings",
                                    ("col name +with_-=special/symbols*%", "-&+=%*&/")],
                         name='power-sweep',
                         data_base_dir=cls._data_root) as m:

      cls._typical_datadir = m.path()
      logging.info(f'This info message will (also) end up in log.txt within the data dir {m.path()}.')

      for p in [-30, -20, -10]:
        VNA_instrument._power = p  # <-- this new value gets automatically stored in the data since its in the snapshot
        m.add_points({'frequency': freqs, 'S21': VNA_instrument(),
                      "col with strings": [ alphabet[i%10::-p//10] for i in range(len(freqs)) ],
                      'col name +with_-=special/symbols*%': np.random.randn(len(freqs))})

    time.sleep(0.5)
    cls._timestamp_between_typical_and_single_row_datadirs = time.time()
    time.sleep(1)

    # Create test dataset with a single row
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=cls._data_root,
                         log_level=logging.WARNING) as m:

      cls._single_row_datadir = m.path()

      for p in [-30]:
        VNA_instrument._power = p
        m.add_point({'frequency': freqs[0], 'S21': VNA_instrument()[0]})


    # Create test dataset with no data rows
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=cls._data_root) as m:

      cls._no_rows_datadir = m.path()

    # Create test dataset with nonstandard/legacy .dat file name
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=cls._data_root,
                         compress=False) as m:

      cls._legacy_datadir = m.path()

      for p in [-30]:
        VNA_instrument._power = p
        m.add_points({'frequency': freqs, 'S21': VNA_instrument()})

    shutil.move(os.path.join(cls._legacy_datadir, 'tabular_data.dat'),
                os.path.join(cls._legacy_datadir, 'differently_named_data.dat'))

    # Create test dataset with a single column
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz")],
                         name='single-col',
                         data_base_dir=cls._data_root) as m:

      cls._single_column_datadir = m.path()

      for p in [-30]:
        VNA_instrument._power = p
        m.add_points({'frequency': freqs})

    # Create test dataset with an empty tabular_data.dat file.
    # Resembles the case of an ongoing measurement where add_points()
    # hasn't been called yet.
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=cls._data_root,
                         compress=False) as m:

      cls._empty_tabulardat_datadir = m.path()

    with open(os.path.join(cls._empty_tabulardat_datadir, 'tabular_data.dat'), 'w') as f: pass

  @classmethod
  def tearDownClass(cls):
    pass
    #import sys
    #print ('\nTests finished.\nPress enter to delete the test data dir created '
    #       f'in the process: {cls._data_root}')
    #sys.stdin.read(1)
    #shutil.rmtree(cls._data_root)

  def test_dataset_files(self):
    original_dir = os.path.abspath('.')
    try:
      os.chdir(self._typical_datadir)

      # Check that we have the files we expect in the data dir
      files = os.listdir('.')

      self.assertTrue("README" in files)
      self.assertTrue("tabular_data.dat.gz" in files)
      self.assertTrue("snapshot.json.gz" in files)
      self.assertTrue("snapshot_diffs.tar.gz" in files)
      self.assertTrue("log.txt" in files)

    finally:
      os.chdir(original_dir)

  def test_dataexplorer_selector(self):
    # Test the graphical dataset selector
    sel = dataexplorer.data_selector(self._data_root)
    self.assertEqual(len(sel.options), 4)
    self.assertTrue(sel.options[0] == os.path.split(self._single_column_datadir)[-1])
    self.assertTrue(sel.options[1] == os.path.split(self._no_rows_datadir)[-1])
    self.assertTrue(sel.options[2] == os.path.split(self._single_row_datadir)[-1])
    self.assertTrue(sel.options[3] == os.path.split(self._typical_datadir)[-1])
    self.assertTrue(sel.options[3].endswith("power-sweep"))
    self.assertTrue(len(sel.value) == 1)
    self.assertTrue(sel.value[0].endswith("single-col"))

    # Test age_filter
    sel = dataexplorer.data_selector(self._data_root,
                                     age_filter=time.time() - self._timestamp_between_typical_and_single_row_datadirs,
                                     return_widget=False)
    self.assertEqual(len(sel), 3)
    self.assertTrue(sel[0] == os.path.split(self._single_column_datadir)[-1])
    self.assertTrue(sel[1] == os.path.split(self._no_rows_datadir)[-1])
    self.assertTrue(sel[2] == os.path.split(self._single_row_datadir)[-1])

    # Test name_filter
    sel = dataexplorer.data_selector(self._data_root,
                                     name_filter="power-sweep",
                                     return_widget=False)
    self.assertEqual(len(sel), 3)

  def test_reading_data(self):
    """ Read back the data saved on disk using dataview. """
    # Test the short-hand syntax for a single data dir
    d = DataView( PDataSingle(self._typical_datadir) )

    # Test the more common syntax where we pass an array of data objects
    d = DataView([ PDataSingle(self._typical_datadir), ])

    # Check sanity of initial snapshot
    self.assertTrue("VNA1" in d.settings()[0][1]['instruments'].keys())
    self.assertTrue("voltage_source1" in d.settings()[0][1]['instruments'].keys())
    self.assertTrue("voltage_source2" in d.settings()[0][1]['instruments'].keys())

    d.add_virtual_dimension('VNA power', units="dBm", from_set=('instruments', 'VNA1', 'power'))
    d.add_virtual_dimension('unicode check', dtype=str, from_set=('instruments', 'voltage_source2', 'strange unicode characters'))

    # Check dimensions and units
    self.assertTrue("frequency" in d.dimensions())
    self.assertTrue(d.units("frequency") == "Hz")
    self.assertTrue("S21" in d.dimensions())
    self.assertTrue(d.units("S21") == "")
    self.assertTrue("VNA power" in d.dimensions())
    self.assertTrue(d.units("VNA power") == "dBm")

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)
    self.assertTrue(len(d["frequency"]) == 3*len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)
    self.assertTrue(max(np.abs(d["frequency"][:len(expected_freqs)] / expected_freqs - 1)) < 1e-10)
    self.assertTrue(max(np.abs(d["frequency"][-len(expected_freqs):] / expected_freqs - 1)) < 1e-10)

    # Check "col with strings": [ alphabet[i%10::-p//10] for i in range(len(freqs)) ],
    self.assertTrue("col with strings" in d.dimensions())
    self.assertTrue(d.units("col with strings") == "")
    self.assertTrue(all( alphabet[i%10::1 + i//len(expected_freqs)] for i,s in enumerate(d["col with strings"]) ))

    # Check handling of unicode characters
    self.assertTrue(all( x == "∰ ᴥ ❽ ⁂" for x in d["unicode check"] ))

    # Check S21
    self.assertTrue(len(d["S21"]) == len(d["frequency"]))

    expected_S21 = resonator_response(expected_freqs, -30)
    self.assertTrue(max(np.abs(d["S21"][:len(expected_freqs)] / expected_S21 - 1)) < 1e-10)

    expected_S21 = resonator_response(expected_freqs, -10)
    self.assertTrue(max(np.abs(d["S21"][-len(expected_freqs):] / expected_S21 - 1)) < 1e-10)

    # Check VNA power virtual column
    self.assertTrue(len(d["VNA power"]) == len(d["frequency"]))

    expected_VNA_powers = [-30, -20, -10]
    self.assertTrue(max(np.abs(d["VNA power"][:len(expected_freqs)] / expected_VNA_powers[0] - 1)) < 1e-10)
    self.assertTrue(max(np.abs(d["VNA power"][-len(expected_freqs):] / expected_VNA_powers[-1] - 1)) < 1e-10)

    # Check that we can parse "key_that_gets_added". It's not there in
    # the initial snapshot that's created when run_measurement() is
    # callled, but is added by the time add_points() is first called.
    d.add_virtual_dimension('key that gets added', dtype=str, from_set=('key_that_gets_added',))
    self.assertTrue(d['key that gets added'][0] == "value_for_key_that_gets_added")
    self.assertTrue(all(v == d['key that gets added'][0] for v in d['key that gets added'] ))

    # Check conversion to xarray
    xa = d.to_xarray("S21", coords=[ "frequency", "VNA power" ])
    self.assertTrue(all(xa.coords["frequency"] == expected_freqs))
    self.assertTrue(all(xa.coords["VNA_power"] == [-30., -20., -10.]))
    self.assertTrue(all(xa.sel(VNA_power=-30) == d["S21"][:len(expected_freqs)] ))
    self.assertTrue(all(xa.sel(VNA_power=-10) == d["S21"][-len(expected_freqs):] ))
    self.assertTrue(xa.S21.attrs["data_source"].strip(')').endswith(self._typical_datadir))

    # Check coarse grained xarray
    xa = d.to_xarray("S21", coords=[ "frequency", "VNA power" ], coarse_graining={"frequency": 11e6})
    self.assertTrue(all(xa.coords["frequency"] == expected_freqs[::3]))
    self.assertTrue(all(xa.coords["VNA_power"] == [-30., -20., -10.]))
    self.assertTrue(all(xa.S21.sel(VNA_power=-30)[:-1] == d["S21"][2:len(expected_freqs):3] ))
    self.assertTrue(all(xa.S21.sel(VNA_power=-10)[:-1] == d["S21"][-(len(expected_freqs)-2)::3] ))
    self.assertTrue(xa.S21.attrs["data_source"].strip(')').endswith(self._typical_datadir))

    # Check conversion to xarray with function spec
    xa = d.to_xarray(("S21", ("scaled_S21", lambda dd: 10*dd["S21"], '')), coords=[ "frequency", "VNA power" ])
    self.assertTrue(all(xa.coords["frequency"] == expected_freqs))
    self.assertTrue(all(xa.coords["VNA_power"] == [-30., -20., -10.]))
    self.assertTrue(all(xa.scaled_S21.sel(VNA_power=-30) == 10*d["S21"][:len(expected_freqs)] ))
    self.assertTrue(all(xa.scaled_S21.sel(VNA_power=-10) == 10*d["S21"][-len(expected_freqs):] ))
    self.assertTrue(xa.scaled_S21.attrs["data_source"].strip(')').endswith(self._typical_datadir))

  def test_reading_data_with_comments(self):
    """ Check that parse_comments=True also works. """
    # Test reading the data with parse_comments=True. Not the best data set since it has no such comments...
    d = DataView([ PDataSingle(self._typical_datadir, parse_comments=True), ])

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)
    self.assertTrue(len(d["frequency"]) == 3*len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)
    self.assertTrue(max(np.abs(d["frequency"][:len(expected_freqs)] / expected_freqs - 1)) < 1e-10)
    self.assertTrue(max(np.abs(d["frequency"][-len(expected_freqs):] / expected_freqs - 1)) < 1e-10)

  def test_reading_legacy_dat_file(self):
    """ Read data from a .dat file with a nonstandard name. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._legacy_datadir), ])

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)
    self.assertTrue(len(d["frequency"]) == len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)

  def test_reading_single_row_data(self):
    """ Read a data set containing just a single row. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._single_row_datadir), ])

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)[:1]
    self.assertTrue(len(d["frequency"]) == len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)

  def test_reading_single_column_data(self):
    """ Read a data set containing just a single column. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._single_column_datadir), ])

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)
    self.assertTrue(len(d["frequency"]) == len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)

  def test_reading_no_rows_data(self):
    """ Read a data set containing no data rows. """
    for d in [ DataView([ PDataSingle(self._no_rows_datadir), ]),
               DataView(PDataSingle(self._no_rows_datadir)) ]:
      self.assertEqual(set(d.dimensions()), set(['S21', 'frequency', 'data_source']))
      self.assertEqual(d["frequency"].size, 0)

  def test_reading_empty_tabular_data(self):
    """ Read a data set containing an empty tabular_data.dat. """
    d = DataView([ PDataSingle(self._empty_tabulardat_datadir), ])
    self.assertEqual(d.dimensions(), ['data_source'])
    d = DataView(PDataSingle(self._empty_tabulardat_datadir))
    self.assertEqual(d.dimensions(), ['data_source'])

  def test_reading_data_with_different_columns(self):
    """ Read data sets containing different columns into a single DataView. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._typical_datadir), PDataSingle(self._single_column_datadir) ])

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)
    self.assertTrue(len(d["frequency"]) == 4*len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"][:41]) / expected_freqs - 1 )) < 1e-10)

  def test_divide_into_sweeps_and_masking(self):
    """ Test divide_into_sweeps(). """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._typical_datadir), ])
    d.add_virtual_dimension('VNA power', units="dBm", from_set=('instruments', 'VNA1', 'power'))

    def check_correctness(s, correct_sweeps=[slice(0, 41, None), slice(41, 82, None), slice(82, 123, None)]):
      self.assertEqual(len(s), len(correct_sweeps))
      self.assertTrue(all( sweep == sweep_correct for sweep, sweep_correct in zip(s, correct_sweeps) ))

    check_correctness(d.divide_into_sweeps("frequency", use_sweep_direction=True))
    check_correctness(d.divide_into_sweeps("VNA power", use_sweep_direction=False))

    # Also test autodetection of use_sweep_direction
    check_correctness(d.divide_into_sweeps("frequency"))
    check_correctness(d.divide_into_sweeps("VNA power"))

    # Test the corner case that we have only one sweep
    d.mask_rows(slice(0, 41, None), unmask_instead=True)
    check_correctness(d.divide_into_sweeps("frequency"), [ slice(0, 41, None) ])
    check_correctness(d.divide_into_sweeps("VNA power"), [ slice(0, 41, None) ])

    # Check that the frequencies are also what we expect, after masking
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)
    self.assertTrue(len(d["frequency"]) == len(expected_freqs))
    self.assertTrue(max(np.abs(d["frequency"] / expected_freqs - 1)) < 1e-10)

    # Test the corner case that we have only one point
    d.mask_rows(slice(0, 1, None), unmask_instead=True)
    self.assertTrue(len(d["frequency"]) == 1)
    self.assertTrue(max(np.abs(d["frequency"] / expected_freqs[:1] - 1)) < 1e-10)
    check_correctness(d.divide_into_sweeps("frequency"), [ slice(0, 1, None) ])
    check_correctness(d.divide_into_sweeps("VNA power"), [ slice(0, 1, None) ])

    # Test removing rows permanently
    d.remove_masked_rows_permanently()
    self.assertTrue(len(d["frequency"]) == 1)
    self.assertTrue(max(np.abs(d["frequency"] / expected_freqs[:1] - 1)) < 1e-10)
    check_correctness(d.divide_into_sweeps("frequency"), [ slice(0, 1, None) ])
    check_correctness(d.divide_into_sweeps("VNA power"), [ slice(0, 1, None) ])

  def test_json_export(self):
    """ Test that exporting the dataview object to JSON works. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._typical_datadir), ])
    import json
    from pdata.helpers import NumpyJSONEncoder
    json.dumps({col: d[col] for col in d.dimensions()}, cls=NumpyJSONEncoder)

  def test_tabular_data_header_parsing(self):
    """Test that parsing tabular data header works as expected, also for
       legacy formats."""
    self.assertTrue(isinstance(PDataSingle._parse_timestamp('2017-12-06 09:15:40.123'), float))

    for version in [ "qcodes legacy",
                     "legacy variant 1",
                     "pre-v1",
                     "v1.0.0" ]:

      if version in ["qcodes legacy", "legacy variant 1", "pre-v1"]:
        expected_name = [ "frequency", "S21", "col name +with_-=special/symbols*%" ]
        expected_units = [ "Hz", "",  "-&+=%*&/"]
        expected_dtype = [ numpy.float64, numpy.float64,  numpy.float64]
      else:
        expected_name = [ "frequency", "S21", "col with strings", "col name +with_-=special/symbols*%" ]
        expected_units = [ "Hz", "", "",  "-&+=%*&/"]
        expected_dtype = [ numpy.float64, numpy.complex128, str, numpy.float64]

      for binary_mode in [True, False]:
        f = example_tabular_data(version, file_object=True, binary_mode=binary_mode)
        f.seek(0); header = PDataSingle._extract_header(f, parse_all_comments=True)
        f.seek(0); header = PDataSingle._extract_header(f, parse_all_comments=False)
        column_names, units = PDataSingle._parse_columns_from_header(header["table_header"])
        dtypes, converters = PDataSingle._parse_dtypes_from_header(header["table_header"], convert_timestamps=True)

        for i in range(3):
          self.assertEqual(expected_name[i], column_names[i])
          if version not in ["qcodes legacy", "legacy variant 1"]:
            self.assertEqual(expected_units[i], units[i])
          if version in [ "v1.0.0" ]:
            self.assertEqual(expected_dtype[i], dtypes[i])

        # Also test inference from data
        inferred_dtypes, inferred_converters = PDataSingle._infer_dtypes_from_first_data_row(header["first_data_row"],
                                                                                             convert_timestamps=True)

  def test_tabular_data_footer_parsing(self):
    """Test that parsing tabular data footer works as expected, also for
       legacy formats."""

    # Test some corner cases
    footer = PDataSingle._parse_footer("Measurement ended at 2023-01-22 13:07:44.551944\n"
                                       "Snapshot diffs preceding rows (0-based index): ")
    self.assertEqual(len(footer["snapshot_diffs_preceding_rows"]), 0)

    footer = PDataSingle._parse_footer("Measurement ended at 2023-01-22 13:07:44.551944\n"
                                       "Snapshot diffs preceding rows (0-based index): 11")
    self.assertTrue(all(i==j for i,j in zip(footer["snapshot_diffs_preceding_rows"], [ 11 ]) ))

    # Test older data format versions too
    for version in [ "qcodes legacy",
                     "legacy variant 1",
                     "pre-v1",
                     "v1.0.0" ]:

      for binary_mode in [True, False]:
        f = example_tabular_data(version, file_object=True, binary_mode=binary_mode)
        f.readlines(); raw_footer = PDataSingle._extract_footer(f)
        footer = PDataSingle._parse_footer(raw_footer)

        if version in ["qcodes legacy", "legacy variant 1", "pre-v1"]:
          # No footer expected
          self.assertEqual(raw_footer.strip(), "")
          self.assertEqual(footer["raw_footer"], raw_footer)
          continue

        expected_ended_at = datetime.datetime.strptime("2023-01-22 13:07:44.551944", '%Y-%m-%d %H:%M:%S.%f')
        self.assertEqual((footer["measurement_ended_at"] - expected_ended_at).seconds, 0)

        expected_diff_rows = [ 0,41,82 ]
        self.assertTrue(all(i==j for i,j in zip(footer["snapshot_diffs_preceding_rows"], expected_diff_rows) ))

  def test_jsondiff_format_consistency(self):
    """Test that jsondiff.diff() produces output compliant with pdata on
       disk fomat v1.0.0. By having this unit test, we can more
       confidently allow use of latest jsondiff version. Otherwise we
       should fix the jsondiff version that pdata depends on.
    """
    import jsondiff
    from pdata.helpers import PdataJSONDiffer

    snap0 = {"a": 0, "b": {"ba": 1, "bb": 2}}
    snap1 = {"a": 0, "b": {"ba": 1, "bb": 3}}
    d = jsondiff.diff(snap0, snap1, cls=PdataJSONDiffer, marshal=True)
    self.assertEqual(d, {'b': {'bb': 3}})

    snap0 = {"a": 0, "b": {"ba": 1, "bb": 2}}
    snap1 = {"a": 0, "b": {"ba": 4, "bb": 3}}
    d = jsondiff.diff(snap0, snap1, cls=PdataJSONDiffer, marshal=True)
    self.assertEqual(d, {'b': {"ba": 4, 'bb': 3}})

    snap0 = {"a": 0, "b": [{"ba": 1, "bb": 2}]}
    snap1 = {"a": 0, "b": [{"ba": 4, "bb": 2}]}
    d = jsondiff.diff(snap0, snap1, cls=PdataJSONDiffer, marshal=True)
    self.assertEqual(d, {'b': {0: {'ba': 4}}})

    snap0 = {"a": 0, "b": {"ba": 1, "bb": 2}}
    snap1 = {"a": 0, "b": {"bb": 3}}
    d = jsondiff.diff(snap0, snap1, cls=PdataJSONDiffer, marshal=True)
    self.assertEqual(d, {'b': {'bb': 3, '$delete': ['ba']}})

    snap0 = {"a": 0, "b": {"ba": 1, "bb": 2}}
    snap1 = {"a": 0, "b": {}}
    d = jsondiff.diff(snap0, snap1, cls=PdataJSONDiffer, marshal=True)
    self.assertEqual(d, {'b': {'$replace': {}}})

def example_tabular_data(version, file_object=False, binary_mode=False):
  """Examples of contents of tabular_data.dat, useful especially for
     testing that parsing of legacy data sets also works."""
  tabular_data_qcodes_legacy = """
# some	other	content
# "frequency"	"S21"	"col name +with_-=special/symbols*%"
# 5
5.900000000000000e+09	9.878581064994841e-01	-8.724404509699187e-01
5.905000000000000e+09	9.868398417340444e-01	-2.716625651538533e-01
5.910000000000000e+09	9.857022708158116e-01	4.430024269210494e-02
5.915000000000000e+09	9.844290657439446e-01	-1.705752478646343e+00
5.920000000000000e+09	9.830018886790357e-01	-4.686516332742403e-03
"""

  tabular_data_legacy_variant1 = """
#
# frequency	S21	col name +with_-=special/symbols*%
#
5.900000000000000e+09	9.878581064994841e-01	-8.724404509699187e-01
5.905000000000000e+09	9.868398417340444e-01	-2.716625651538533e-01
5.910000000000000e+09	9.857022708158116e-01	4.430024269210494e-02
5.915000000000000e+09	9.844290657439446e-01	-1.705752478646343e+00
5.920000000000000e+09	9.830018886790357e-01	-4.686516332742403e-03
"""

  tabular_data_pre_v1 = """
# 
# frequency (Hz)	S21 ()	col name +with_-=special/symbols*% (-&+=%*&/)
# 
5.900000000000000e+09	9.878581064994841e-01	-8.724404509699187e-01
5.905000000000000e+09	9.868398417340444e-01	-2.716625651538533e-01
5.910000000000000e+09	9.857022708158116e-01	4.430024269210494e-02
5.915000000000000e+09	9.844290657439446e-01	-1.705752478646343e+00
5.920000000000000e+09	9.830018886790357e-01	-4.686516332742403e-03
"""

  tabular_data_v1_0_0 = """
#
# ondisk_format_version = 1.0.0
# pdata_version = 2.0.0
# jsondiff_version = 2.0.0
# numpy_version = 1.22.4
# python_version = 3.10.4 | packaged by conda-forge | (main, Mar 24 2022, 17:38:57) [GCC 10.3.0]
# Measurement started at 2023-01-22 13:07:44.540987
# Column dtypes: numpy.float64	numpy.complex128	builtins.str	numpy.float64
#
# frequency (Hz)	S21 ()	col with strings ()	col name +with_-=special/symbols*% (-&+=%*&/)
#
5.900000000000000e+09	9.878581064994841e-01-2.380763431473693e-02j	adgjmpsvy	-8.724404509699187e-01
5.905000000000000e+09	9.868398417340444e-01-2.451402029932909e-02j	behknqtwz	-2.716625651538533e-01
5.910000000000000e+09	9.857022708158116e-01-2.523128679562658e-02j	cfilorux	4.430024269210494e-02
5.915000000000000e+09	9.844290657439446e-01-2.595155709342560e-02j	dgjmpsvy	-1.705752478646343e+00
5.920000000000000e+09	9.830018886790357e-01-2.666370403288523e-02j	ehknqtwz	-4.686516332742403e-03
5.925000000000000e+09	9.814004376367614e-01-2.735229759299781e-02j	filorux	-5.647983875322222e-01
5.930000000000000e+09	9.796027196373817e-01-2.799626716437809e-02j	gjmpsvy	2.400845163753200e-01
5.935000000000000e+09	9.775857017286844e-01-2.856724289481395e-02j	hknqtwz	-3.958497585610498e-01
5.940000000000000e+09	9.753265602322206e-01-2.902757619738752e-02j	ilorux	1.465991270647432e-02
5.945000000000000e+09	9.728048346960541e-01-2.932811944543192e-02j	jmpsvy	-9.144260542735150e-02
5.950000000000000e+09	9.700058811997647e-01-2.940599882376005e-02j	adgjmpsvy	-1.122703098235154e+00
5.955000000000000e+09	9.669260700389105e-01-2.918287937743190e-02j	behknqtwz	-9.704102683578877e-01
5.960000000000000e+09	9.635800999761961e-01-2.856462746965009e-02j	cfilorux	1.112841392481274e-01
5.965000000000000e+09	9.600104547830632e-01-2.744380554103502e-02j	dgjmpsvy	1.316037916747176e-01
5.970000000000000e+09	9.562982005141388e-01-2.570694087403599e-02j	ehknqtwz	5.702316493396783e-01
5.975000000000000e+09	9.525728456292623e-01-2.324860508369498e-02j	filorux	-3.469153895948848e-01
5.980000000000000e+09	9.490169943352216e-01-1.999333555481506e-02j	gjmpsvy	-3.512625232363753e-01
5.985000000000000e+09	9.458598726114650e-01-1.592356687898089e-02j	hknqtwz	-1.512759832768233e+00
5.990000000000000e+09	9.433543132173269e-01-1.110699740836727e-02j	ilorux	4.430139762347148e-02
5.995000000000000e+09	9.417364813404417e-01-5.712109672505713e-03j	jmpsvy	-1.968944068718038e+00
6.000000000000000e+09	9.411764705882353e-01+0.000000000000000e+00j	adgjmpsvy	3.146637998788404e-01
6.005000000000000e+09	9.417364813404417e-01+5.712109672505713e-03j	behknqtwz	-2.923734738008148e-01
6.010000000000000e+09	9.433543132173269e-01+1.110699740836727e-02j	cfilorux	1.577570853173502e+00
6.015000000000000e+09	9.458598726114650e-01+1.592356687898089e-02j	dgjmpsvy	1.633651926046173e+00
6.020000000000000e+09	9.490169943352216e-01+1.999333555481506e-02j	ehknqtwz	-1.686837396627811e-01
6.025000000000000e+09	9.525728456292623e-01+2.324860508369498e-02j	filorux	8.122426709483470e-02
6.030000000000000e+09	9.562982005141388e-01+2.570694087403599e-02j	gjmpsvy	-8.158835358420073e-02
6.035000000000000e+09	9.600104547830632e-01+2.744380554103502e-02j	hknqtwz	-5.188558128303026e-01
6.040000000000000e+09	9.635800999761961e-01+2.856462746965009e-02j	ilorux	7.374968718655751e-01
6.045000000000000e+09	9.669260700389105e-01+2.918287937743190e-02j	jmpsvy	1.515119780767486e+00
6.050000000000000e+09	9.700058811997647e-01+2.940599882376005e-02j	adgjmpsvy	1.498439912783504e+00
6.055000000000000e+09	9.728048346960541e-01+2.932811944543192e-02j	behknqtwz	7.041099103877755e-01
6.060000000000000e+09	9.753265602322206e-01+2.902757619738752e-02j	cfilorux	8.450695337086743e-01
6.065000000000000e+09	9.775857017286844e-01+2.856724289481395e-02j	dgjmpsvy	-1.367103275818633e+00
6.070000000000000e+09	9.796027196373817e-01+2.799626716437809e-02j	ehknqtwz	1.355728278769259e+00
6.075000000000000e+09	9.814004376367614e-01+2.735229759299781e-02j	filorux	-2.385926073154242e-01
6.080000000000000e+09	9.830018886790357e-01+2.666370403288523e-02j	gjmpsvy	-5.776159853057284e-01
6.085000000000000e+09	9.844290657439446e-01+2.595155709342560e-02j	hknqtwz	-5.475101103735122e-01
6.090000000000000e+09	9.857022708158116e-01+2.523128679562658e-02j	ilorux	-7.303110778011148e-01
6.095000000000000e+09	9.868398417340444e-01+2.451402029932909e-02j	jmpsvy	6.066919174570521e-01
6.100000000000000e+09	9.878581064994841e-01+2.380763431473693e-02j	adgjmpsvy	7.777373602378879e-01
5.900000000000000e+09	9.924503681610588e-01-2.796159940348588e-02j	acegikmoqsuwy	-5.367972538237084e-01
5.905000000000000e+09	9.916957145786344e-01-2.921878203813820e-02j	bdfhjlnprtvxz	2.692140476068353e+00
5.910000000000000e+09	9.908256880733944e-01-3.058103975535168e-02j	cegikmoqsuwy	-9.092298603710668e-01
5.915000000000000e+09	9.898164445561981e-01-3.205934121196882e-02j	dfhjlnprtvxz	-1.728654628304821e-01
5.920000000000000e+09	9.886379576378174e-01-3.366531070276337e-02j	egikmoqsuwy	-5.475713617567546e-01
5.925000000000000e+09	9.872521246458923e-01-3.541076487252125e-02j	fhjlnprtvxz	5.537776420353869e-01
5.930000000000000e+09	9.856102327233967e-01-3.730680405045302e-02j	gikmoqsuwy	-9.611708365999772e-01
5.935000000000000e+09	9.836495761001212e-01-3.936213161081954e-02j	hjlnprtvxz	8.995543994736364e-02
5.940000000000000e+09	9.812889812889813e-01-4.158004158004158e-02j	ikmoqsuwy	-4.503918066902822e-01
5.945000000000000e+09	9.784230154501865e-01-4.395311667554608e-02j	jlnprtvxz	-3.580980056628063e-01
5.950000000000000e+09	9.749148343140291e-01-4.645401052957572e-02j	acegikmoqsuwy	-1.072733724340073e+00
5.955000000000000e+09	9.705882352941176e-01-4.901960784313725e-02j	bdfhjlnprtvxz	4.980151515763669e-01
5.960000000000000e+09	9.652211249463289e-01-5.152425933877201e-02j	cegikmoqsuwy	-3.015042618239792e-01
5.965000000000000e+09	9.585465711361310e-01-5.373592630501535e-02j	dfhjlnprtvxz	-1.262766679696165e+00
5.970000000000000e+09	9.502762430939227e-01-5.524861878453038e-02j	egikmoqsuwy	3.584223633673357e-01
5.975000000000000e+09	9.401772525849336e-01-5.539143279172820e-02j	fhjlnprtvxz	-4.030517173722464e-01
5.980000000000000e+09	9.282550930026572e-01-5.314437555358723e-02j	gikmoqsuwy	-9.916129928239104e-01
5.985000000000000e+09	9.150943396226415e-01-4.716981132075471e-02j	hjlnprtvxz	-1.626821800896090e+00
5.990000000000000e+09	9.022919179734620e-01-3.618817852834740e-02j	ikmoqsuwy	1.388939647345820e+00
5.995000000000000e+09	8.925729442970822e-01-1.989389920424402e-02j	jlnprtvxz	1.903500865450215e+00
6.000000000000000e+09	8.888888888888888e-01+0.000000000000000e+00j	acegikmoqsuwy	-5.317958572079927e-01
6.005000000000000e+09	8.925729442970822e-01+1.989389920424402e-02j	bdfhjlnprtvxz	5.593776458748464e-02
6.010000000000000e+09	9.022919179734620e-01+3.618817852834740e-02j	cegikmoqsuwy	2.993419066745532e-01
6.015000000000000e+09	9.150943396226415e-01+4.716981132075471e-02j	dfhjlnprtvxz	1.041335220054504e-01
6.020000000000000e+09	9.282550930026572e-01+5.314437555358723e-02j	egikmoqsuwy	2.773581074066093e-01
6.025000000000000e+09	9.401772525849336e-01+5.539143279172820e-02j	fhjlnprtvxz	-7.995842868856885e-01
6.030000000000000e+09	9.502762430939227e-01+5.524861878453038e-02j	gikmoqsuwy	-3.703549554676884e-01
6.035000000000000e+09	9.585465711361310e-01+5.373592630501535e-02j	hjlnprtvxz	-2.054408344868714e+00
6.040000000000000e+09	9.652211249463289e-01+5.152425933877201e-02j	ikmoqsuwy	2.013145119661018e+00
6.045000000000000e+09	9.705882352941176e-01+4.901960784313725e-02j	jlnprtvxz	4.529533979416627e-01
6.050000000000000e+09	9.749148343140291e-01+4.645401052957572e-02j	acegikmoqsuwy	7.304022856052758e-01
6.055000000000000e+09	9.784230154501865e-01+4.395311667554608e-02j	bdfhjlnprtvxz	4.417491153117528e-01
6.060000000000000e+09	9.812889812889813e-01+4.158004158004158e-02j	cegikmoqsuwy	8.942016233964308e-01
6.065000000000000e+09	9.836495761001212e-01+3.936213161081954e-02j	dfhjlnprtvxz	-3.511500584044973e-01
6.070000000000000e+09	9.856102327233967e-01+3.730680405045302e-02j	egikmoqsuwy	-9.839876725909419e-01
6.075000000000000e+09	9.872521246458923e-01+3.541076487252125e-02j	fhjlnprtvxz	1.560751196594876e+00
6.080000000000000e+09	9.886379576378174e-01+3.366531070276337e-02j	gikmoqsuwy	9.515170667940354e-01
6.085000000000000e+09	9.898164445561981e-01+3.205934121196882e-02j	hjlnprtvxz	2.032098414538235e-01
6.090000000000000e+09	9.908256880733944e-01+3.058103975535168e-02j	ikmoqsuwy	1.257736241206638e+00
6.095000000000000e+09	9.916957145786344e-01+2.921878203813820e-02j	jlnprtvxz	-7.205030301781029e-01
6.100000000000000e+09	9.924503681610588e-01+2.796159940348588e-02j	acegikmoqsuwy	3.381896932985366e-02
5.900000000000000e+09	9.955990220048899e-01-2.933985330073350e-02j	abcdefghijklmnopqrstuvwxyz	5.772825924303353e-01
5.905000000000000e+09	9.951351351351352e-01-3.081081081081082e-02j	bcdefghijklmnopqrstuvwxyz	-3.048725003124251e-01
5.910000000000000e+09	9.945945945945946e-01-3.243243243243243e-02j	cdefghijklmnopqrstuvwxyz	2.297532989063409e-01
5.915000000000000e+09	9.939597315436242e-01-3.422818791946309e-02j	defghijklmnopqrstuvwxyz	3.794488470739131e-01
5.920000000000000e+09	9.932075471698113e-01-3.622641509433962e-02j	efghijklmnopqrstuvwxyz	-1.518809183801459e-02
5.925000000000000e+09	9.923076923076923e-01-3.846153846153846e-02j	fghijklmnopqrstuvwxyz	3.470425690084502e-01
5.930000000000000e+09	9.912195121951219e-01-4.097560975609757e-02j	ghijklmnopqrstuvwxyz	1.542572983764280e+00
5.935000000000000e+09	9.898876404494382e-01-4.382022471910113e-02j	hijklmnopqrstuvwxyz	-5.718229073701991e-01
5.940000000000000e+09	9.882352941176471e-01-4.705882352941176e-02j	ijklmnopqrstuvwxyz	5.508049038299994e-01
5.945000000000000e+09	9.861538461538462e-01-5.076923076923077e-02j	jklmnopqrstuvwxyz	-5.366515288674258e-01
5.950000000000000e+09	9.834862385321100e-01-5.504587155963303e-02j	abcdefghijklmnopqrstuvwxyz	1.426922384577318e+00
5.955000000000000e+09	9.800000000000000e-01-6.000000000000000e-02j	bcdefghijklmnopqrstuvwxyz	-9.292230448886548e-01
5.960000000000000e+09	9.753424657534246e-01-6.575342465753425e-02j	cdefghijklmnopqrstuvwxyz	-6.741798996362659e-01
5.965000000000000e+09	9.689655172413794e-01-7.241379310344828e-02j	defghijklmnopqrstuvwxyz	-2.499210639107734e+00
5.970000000000000e+09	9.600000000000000e-01-8.000000000000002e-02j	efghijklmnopqrstuvwxyz	-9.479734233919107e-02
5.975000000000000e+09	9.470588235294117e-01-8.823529411764706e-02j	fghijklmnopqrstuvwxyz	1.310824652829232e+00
5.980000000000000e+09	9.279999999999999e-01-9.600000000000003e-02j	ghijklmnopqrstuvwxyz	9.755538670431033e-01
5.985000000000000e+09	9.000000000000000e-01-1.000000000000000e-01j	hijklmnopqrstuvwxyz	5.172358727492180e-02
5.990000000000000e+09	8.615384615384616e-01-9.230769230769230e-02j	ijklmnopqrstuvwxyz	-4.561121243194047e-01
5.995000000000000e+09	8.200000000000001e-01-5.999999999999999e-02j	jklmnopqrstuvwxyz	7.899602419438023e-01
6.000000000000000e+09	8.000000000000000e-01+0.000000000000000e+00j	abcdefghijklmnopqrstuvwxyz	-2.172007329151479e+00
6.005000000000000e+09	8.200000000000001e-01+5.999999999999999e-02j	bcdefghijklmnopqrstuvwxyz	5.183055461944829e-01
6.010000000000000e+09	8.615384615384616e-01+9.230769230769230e-02j	cdefghijklmnopqrstuvwxyz	1.889289698198511e+00
6.015000000000000e+09	9.000000000000000e-01+1.000000000000000e-01j	defghijklmnopqrstuvwxyz	2.877427594138673e-01
6.020000000000000e+09	9.279999999999999e-01+9.600000000000003e-02j	efghijklmnopqrstuvwxyz	-2.477269697049949e-01
6.025000000000000e+09	9.470588235294117e-01+8.823529411764706e-02j	fghijklmnopqrstuvwxyz	1.255199573678965e+00
6.030000000000000e+09	9.600000000000000e-01+8.000000000000002e-02j	ghijklmnopqrstuvwxyz	-4.909090027732107e-01
6.035000000000000e+09	9.689655172413794e-01+7.241379310344828e-02j	hijklmnopqrstuvwxyz	-1.535586936266998e+00
6.040000000000000e+09	9.753424657534246e-01+6.575342465753425e-02j	ijklmnopqrstuvwxyz	-1.087014179479258e+00
6.045000000000000e+09	9.800000000000000e-01+6.000000000000000e-02j	jklmnopqrstuvwxyz	-7.200837290292773e-01
6.050000000000000e+09	9.834862385321100e-01+5.504587155963303e-02j	abcdefghijklmnopqrstuvwxyz	-7.192262465107833e-01
6.055000000000000e+09	9.861538461538462e-01+5.076923076923077e-02j	bcdefghijklmnopqrstuvwxyz	1.648885157634419e-01
6.060000000000000e+09	9.882352941176471e-01+4.705882352941176e-02j	cdefghijklmnopqrstuvwxyz	2.459688852542646e-01
6.065000000000000e+09	9.898876404494382e-01+4.382022471910113e-02j	defghijklmnopqrstuvwxyz	1.349180820898145e+00
6.070000000000000e+09	9.912195121951219e-01+4.097560975609757e-02j	efghijklmnopqrstuvwxyz	4.430304612032940e-01
6.075000000000000e+09	9.923076923076923e-01+3.846153846153846e-02j	fghijklmnopqrstuvwxyz	-6.550106626580532e-01
6.080000000000000e+09	9.932075471698113e-01+3.622641509433962e-02j	ghijklmnopqrstuvwxyz	1.292650901517886e-02
6.085000000000000e+09	9.939597315436242e-01+3.422818791946309e-02j	hijklmnopqrstuvwxyz	7.638167432775674e-01
6.090000000000000e+09	9.945945945945946e-01+3.243243243243243e-02j	ijklmnopqrstuvwxyz	-9.593906756765475e-01
6.095000000000000e+09	9.951351351351352e-01+3.081081081081082e-02j	jklmnopqrstuvwxyz	-1.928667867827833e-01
6.100000000000000e+09	9.955990220048899e-01+2.933985330073350e-02j	abcdefghijklmnopqrstuvwxyz	6.032126570983756e-01
#
# Measurement ended at 2023-01-22 13:07:44.551944
# Snapshot diffs preceding rows (0-based index): 0,41,82
"""

  tabular_data = { "qcodes legacy": tabular_data_qcodes_legacy,
                   "legacy variant 1": tabular_data_legacy_variant1,
                   "pre-v1": tabular_data_pre_v1,
                   "v1.0.0": tabular_data_v1_0_0 }[version]

  if not file_object: return tabular_data

  return io.BytesIO(bytes(tabular_data, "utf-8")) if binary_mode else io.StringIO(tabular_data)

if __name__ == '__main__':
  unittest.main(exit=False)
