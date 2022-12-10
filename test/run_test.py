
import logging
import os
import shutil
import tempfile
import time

import unittest

import numpy as np
import numpy.random

from pdata.procedural_data import run_measurement
from pdata.analysis.dataview import DataView, PDataSingle
from pdata.analysis import dataexplorer

lorenzian = lambda f,gamma,f0=6e9: 1/np.pi * (gamma**2 / ((f-f0)**2 + gamma**2))

class TestSavingAndAnalysis(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    """ Create some fake data and save it on disk. """

    cls._data_root = tempfile.mkdtemp(prefix='pdata_test_')
    cls._typical_datadir = None

    freqs = np.linspace(5.9e9, 6.1e9, 41)

    def VNA_instrument():
      """ Fake VNA "instrument" that retuns a list of |S21| that depends on a power parameter. """
      return lorenzian(freqs, 10e6 * 2**(VNA_instrument._power/10.))

    VNA_instrument._power = 10. # Initial value

    def get_instrument_snapshot():
      """ Fake snapshot of instrument parameters. """
      snap = { 'instruments': {
        "VNA1": { "power": VNA_instrument._power, "RBW": 10e3,
                  "freqs": freqs,
                  "random_scalar": np.random.randn(),
                  "random_list": np.random.randn(10).tolist(),
                  "random_ndarray": np.random.randn(10)
        },
        "voltage_source1": { "V": -1.234 },
        "voltage_source2": { "V": -1.234 },
      }}

      if get_instrument_snapshot.counter % 2 == 0: snap["key_that_gets_removed"] = "value_for_key_that_gets_removed"

      if get_instrument_snapshot.counter > 0: snap["key_that_gets_added"] = "value_for_key_that_gets_added"

      get_instrument_snapshot.counter += 1
      return snap

    get_instrument_snapshot.counter = 0

    # Create typical dataset
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21",
                                    ("col +with_-=special/symbols*%", "-&+=%*&/")],
                         name='power-sweep',
                         data_base_dir=cls._data_root) as m:

      cls._typical_datadir = m.path()
      logging.info(f'This info message will (also) end up in log.txt within the data dir {m.path()}.')

      for p in [-30, -20, -10]:
        VNA_instrument._power = p  # <-- this new value gets automatically stored in the data since its in the snapshot
        m.add_points({'frequency': freqs, 'S21': VNA_instrument(),
                      'col +with_-=special/symbols*%': np.random.randn(len(freqs))})

    time.sleep(0.5)
    cls._timestamp_between_typical_and_single_row_datadirs = time.time()
    time.sleep(1)

    # Create test dataset with a single row
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=cls._data_root) as m:

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
    self.assertTrue(len(sel.options) == 4)
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
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._typical_datadir), ])

    # Check sanity of initial snapshot
    self.assertTrue("VNA1" in d.settings()[0][1]['instruments'].keys())
    self.assertTrue("voltage_source1" in d.settings()[0][1]['instruments'].keys())
    self.assertTrue("voltage_source2" in d.settings()[0][1]['instruments'].keys())

    d.add_virtual_dimension('VNA power', units="dBm", from_set=('instruments', 'VNA1', 'power'))

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

    # Check S21
    self.assertTrue(len(d["S21"]) == len(d["frequency"]))

    expected_S21 = lorenzian(expected_freqs, 10e6 * 2**(-30/10.))
    self.assertTrue(max(np.abs(d["S21"][:len(expected_freqs)] / expected_S21 - 1)) < 1e-10)

    expected_S21 = lorenzian(expected_freqs, 10e6 * 2**(-10/10.))
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
    self.assertTrue(xa.attrs["data_source"].strip(')').endswith(self._typical_datadir))

    # Check coarse grained xarray
    xa = d.to_xarray("S21", coords=[ "frequency", "VNA power" ], coarse_graining={"frequency": 11e6})
    self.assertTrue(all(xa.coords["frequency"] == expected_freqs[::3]))
    self.assertTrue(all(xa.coords["VNA_power"] == [-30., -20., -10.]))
    self.assertTrue(all(xa.sel(VNA_power=-30)[:-1] == d["S21"][2:len(expected_freqs):3] ))
    self.assertTrue(all(xa.sel(VNA_power=-10)[:-1] == d["S21"][-(len(expected_freqs)-2)::3] ))
    self.assertTrue(xa.attrs["data_source"].strip(')').endswith(self._typical_datadir))

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
    #time.sleep(2); print(d["frequency"])
    self.assertTrue(len(d["frequency"]) == len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)

  def test_reading_no_rows_data(self):
    """ Read a data set containing no data rows. """
    d = DataView([ PDataSingle(self._no_rows_datadir), ])
    self.assertTrue(len(d["frequency"]) == 0)

  def test_divide_into_sweeps_and_masking(self):
    """ Test divide_into_sweeps(). """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._typical_datadir), ])
    d.add_virtual_dimension('VNA power', units="dBm", from_set=('instruments', 'VNA1', 'power'))

    def check_correctness(s, correct_sweeps=[slice(0, 41, None), slice(41, 82, None), slice(82, 123, None)]):
      self.assertEqual(len(s), len(correct_sweeps))
      #print(correct_sweeps)
      #print(s)
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

  def test_json_export(self):
    """ Test that exporting the dataview object to JSON works. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._typical_datadir), ])
    import json
    from pdata.helpers import NumpyJSONEncoder
    json.dumps({col: d[col] for col in d.dimensions()}, cls=NumpyJSONEncoder)

if __name__ == '__main__':
  unittest.main(exit=False)
