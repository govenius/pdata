
import logging
import os
import shutil
import tempfile

import unittest

import numpy as np

from pdata.procedural_data import run_measurement
from pdata.analysis.dataview import DataView, PDataSingle
from pdata.analysis import dataexplorer

_data_root = tempfile.mkdtemp(prefix='pdata_test_')
_last_datadir = None

class TestExamples(unittest.TestCase):

  def setUp(self):
    pass

  def tearDown(self):
    pass

  def test_000_saving_data(self):
    """ Create some fake data and save it on disk. """

    freqs = np.linspace(5.9e9, 6.1e9, 41)
    lorenzian = lambda f,gamma,f0=6e9: 1/np.pi * (gamma**2 / ((f-f0)**2 + gamma**2))

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

    with run_measurement(get_instrument_snapshot,
                         columns = [("frequency", "Hz"),
                                    "S21"],
                         name='power-sweep',
                         data_base_dir=_data_root) as m:

      _last_datadir = m.path()
      logging.info(f'This info message will (also) end up in log.txt within the data dir {m.path()}.')

      for p in [-30, -20, -10]:
        VNA_instrument._power = p  # <-- this new value gets automatically stored in the data since its in the snapshot
        m.add_points({'frequency': freqs, 'S21': VNA_instrument()})

    original_dir = os.path.abspath('.')
    try:
      os.chdir(_last_datadir)

      # Check that we have the files we expect in the data dir
      files = os.listdir('.')

      self.assertTrue("README" in files)
      self.assertTrue("tabular_data.dat.gz" in files)
      self.assertTrue("snapshot.json.gz" in files)
      self.assertTrue("snapshot_diffs.tar.gz" in files)
      self.assertTrue("log.txt" in files)

    finally:
      os.chdir(original_dir)

  #def test_001_reading_data(self):
  #  """ Read back the data saved on disk. """
    assert _last_datadir!=None, "This test can only be ran after running test_saving_data()."

    # Test the graphical dataset selector
    sel = dataexplorer.data_selector(_data_root)
    self.assertTrue(len(sel.options) == 1)
    self.assertTrue(sel.options[0].endswith("power-sweep"))
    self.assertTrue(len(sel.value) == 1)
    self.assertTrue(sel.value[0].endswith("power-sweep"))

    # Test reading the data using DataView
    d = DataView([ PDataSingle(_last_datadir), ]) # <-- You can concatenate multiple data dirs by adding multiple PDataSingle's to the array

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

if __name__ == '__main__':
  unittest.main(exit=False)

  #import sys
  #print ('\nTests finished.\nPress enter to delete the test data dir created '
  #       f'in the process: {_data_root}')
  #sys.stdin.read(1)
  #shutil.rmtree(_data_root)
