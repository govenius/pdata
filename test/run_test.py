
import logging
import os
import shutil
import tempfile

import unittest

import numpy as np

from pdata.procedural_data import run_measurement
from pdata.analysis.dataview import DataView, PDataSingle
from pdata.analysis import dataexplorer

lorenzian = lambda f,gamma,f0=6e9: 1/np.pi * (gamma**2 / ((f-f0)**2 + gamma**2))

class TestSavingAndAnalysis(unittest.TestCase):

  def setUp(self):
    """ Create some fake data and save it on disk. """

    self._data_root = tempfile.mkdtemp(prefix='pdata_test_')
    self._typical_datadir = None

    freqs = np.linspace(5.9e9, 6.1e9, 41)

    def VNA_instrument():
      """ Fake VNA "instrument" that retuns a list of |S21| that depends on a power parameter. """
      return lorenzian(freqs, 10e6 * 2**(VNA_instrument._power/10.))

    VNA_instrument._power = 10. # Initial value

    def get_instrument_snapshot():
      """ Fake snapshot of instrument parameters. """
      return { 'instruments': {
        "VNA1": { "power": VNA_instrument._power, "RBW": 10e3 },
        "voltage_source1": { "V": -1.234 },
        "voltage_source2": { "V": -1.234 },
      }}

    # Create typical dataset
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=self._data_root) as m:

      self._typical_datadir = m.path()
      logging.info(f'This info message will (also) end up in log.txt within the data dir {m.path()}.')

      for p in [-30, -20, -10]:
        VNA_instrument._power = p  # <-- this new value gets automatically stored in the data since its in the snapshot
        m.add_points({'frequency': freqs, 'S21': VNA_instrument()})

    # Create dataset with a single row
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=self._data_root) as m:

      self._single_row_datadir = m.path()
      logging.info(f'This info message will (also) end up in log.txt within the data dir {m.path()}.')

      for p in [-30]:
        VNA_instrument._power = p  # <-- this new value gets automatically stored in the data since its in the snapshot
        m.add_point({'frequency': freqs[0], 'S21': VNA_instrument()[0]})


    # Create dataset with nonstandard/legacy .dat file name
    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=self._data_root,
                         compress=False) as m:

      self._legacy_datadir = m.path()
      logging.info(f'This info message will (also) end up in log.txt within the data dir {m.path()}.')

      for p in [-30]:
        VNA_instrument._power = p  # <-- this new value gets automatically stored in the data since its in the snapshot
        m.add_points({'frequency': freqs, 'S21': VNA_instrument()})

    shutil.move(os.path.join(self._legacy_datadir, 'tabular_data.dat'),
                os.path.join(self._legacy_datadir, 'differently_named_data.dat'))

  def tearDown(self):
    pass
    #import sys
    #print ('\nTests finished.\nPress enter to delete the test data dir created '
    #       f'in the process: {self._data_root}')
    #sys.stdin.read(1)
    #shutil.rmtree(self._data_root)

  def test_000_dataset_files(self):
    """ Check that the data set written on disk contains the expected files """
    assert self._typical_datadir!=None, "This test can only be ran after saving a data set on disk."

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

  def test_001_dataexplorer_selector(self):
    """ Test that data_selector returns something reasonable. """
    assert self._typical_datadir!=None, "This test can only be ran after saving a data set on disk."

    # Test the graphical dataset selector
    sel = dataexplorer.data_selector(self._data_root)
    self.assertTrue(len(sel.options) == 2)
    self.assertTrue(sel.options[0].endswith("power-sweep"))
    self.assertTrue(len(sel.value) == 1)
    self.assertTrue(sel.value[0].endswith("power-sweep"))

  def test_002_reading_data(self):
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

  def test_006_reading_legacy_dat_file(self):
    """ Read data from a .dat file with a nonstandard name. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._legacy_datadir), ])

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)
    self.assertTrue(len(d["frequency"]) == len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)

  def test_004_reading_single_row_data(self):
    """ Read a data set containing just a single row. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._single_row_datadir), ])

    # Check frequencies
    expected_freqs = np.linspace(5.9e9, 6.1e9, 41)[:1]
    self.assertTrue(len(d["frequency"]) == len(expected_freqs))
    self.assertTrue(max(np.abs( np.unique(d["frequency"]) / expected_freqs - 1 )) < 1e-10)

  def test_003_divide_into_sweeps_and_masking(self):
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

  def test_005_json_export(self):
    """ Test that exporting the dataview object to JSON works. """
    # Test reading the data using DataView
    d = DataView([ PDataSingle(self._typical_datadir), ])
    import json
    from pdata.helpers import NumpyJSONEncoder
    json.dumps({col: d[col] for col in d.dimensions()}, cls=NumpyJSONEncoder)

if __name__ == '__main__':
  unittest.main(exit=False)
