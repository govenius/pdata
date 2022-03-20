.. pdata documentation master file, created by sphinx-quickstart
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


pdata: Simple-to-understand and robust data storage for experimental data
=========================================================================

This procedural data storage package provides a self-contained
interface for storing experimental data using an approach that is
independent from intricasies of broader measurement frameworks. The
main goals are to provide an interface that is:

  * Maximizes the amount of automatically stored metadata, both at the start of a measurement but also changes to parameters **during** the measurement.
  * "Procedural" rather than "functional" in terms of the API the experimenter sees, as procedural programming tends to be easier to understand for a typical experimental physicist who is not a thoroughly trained programmer.
  * The API aims to be self-explanatory, wherever possible.

In practice, this means that pdata has an explicit add_points(<new
data points>) function that adds new points. In addition pdata saves a
diff of instrument parameters each time add_points() is called.

Saving data in measurement script
---------------------------------

You can find an example of running a measurement using `QCoDeS
<https://github.com/QCoDeS/Qcodes>`_ for instrument control but pdata
for data storage and regular python for loops etc. for flow control
under the :code:`examples` directory.

The essential part of running the measurement is::

  # Define a function that gets the current instrument settings from QCoDeS (as a dict)
  import qcodes.station
  get_qcodes_instrument_snapshot = lambda s=qcodes.station.Station.default: s.snapshot(update=True)

  # Columns are specified as (<name>, <unit>), or just <name> if the quantity is dimensionless.
  with run_measurement(get_qcodes_instrument_snapshot,
                       columns = [("frequency", "Hz"),
                                  "S21"],
                       name='power-sweep', data_base_dir=data_root) as m:

    logging.warning('This test warning will (also) end up in log.txt within the data dir.')

    data_path = m.path()
    logging.warning(f'Data directory path = {m.path()}.')

    for p in [-30, -20, -10]:
      vna.power(p) # <-- note that this new value gets automatically stored in the data
      freqs, s21 = vna.acquire_S21()
      m.add_points({'frequency': freqs, 'S21': s21})

Reading data in analysis scripts
--------------------------------

Here is how you read the data back from the above example using DataView::

  from pdata.analysis.dataview import DataView, PDataSingle

  d = DataView([ PDataSingle(data_path), ]) # <-- You can concatenate multiple data dirs by adding multiple PDataSingle's to the array

  print('Instruments in the snapshot file:')
  print(d.settings()[0][1]['instruments'].keys())

  # Add a "column" to the data table based on a value from the snapshot.
  d.add_virtual_dimension('VNA power',
                          from_set=('instruments', 'vna',
                                    'parameters', 'power', 'value'))

  # You can now access the columns by name:
  print('\nFirst few frequencies: %s' % (d["frequency"][:5]))
  print('First few powers: %s' % (d["VNA power"][:5]))

  print('\nUnique powers in the data set: %s' % (np.unique(d["VNA power"])))

  print('\nSweeps based on a per-sweep-fixed parameter: %s' % d.divide_into_sweeps('VNA power'))

  print('\nSweeps based on a per-sweep-swept parameter: %s' % d.divide_into_sweeps('frequency'))

Which outputs the following from the print statements::

  Instruments in the snapshot file:
  dict_keys(['vna'])

  First few frequencies: [5.900e+09 5.905e+09 5.910e+09 5.915e+09 5.920e+09]
  First few powers: [-30. -30. -30. -30. -30.]

  Unique powers in the data set: [-30. -20. -10.]

  Sweeps based on a per-sweep-fixed parameter: [slice(0, 41, None), slice(41, 82, None), slice(82, 123, None)]

  Sweeps based on a per-sweep-swept parameter: [slice(0, 41, None), slice(41, 82, None), slice(82, 123, None)]

In many cases, you would next use code:`divide_into_sweeps` to plot your data ::

  fig, ax = plt.subplots()

  for s in d.divide_into_sweeps('frequency'):
  #for s in d.divide_into_sweeps('VNA power'):  # <-- This would work equally well.
    dd = d.copy(); dd.mask_rows(s, unmask_instead=True)
    power = dd.single_valued_parameter('VNA power')
    ax.plot(dd['frequency'], dd['S21'], label="%s dBm" % power)

  ax.set(xlabel='f (Hz)', ylabel='S21')
  ax.set_yscale('log')
  ax.legend();

Data format
-----------

The goal of the data format is to be self-documenting, such that it is
possible to figure out what it is, even without the pdata source or
binary package. Therefore the data format is:

  * Relatively verbose (i.e. **not** optimized for size).
  * Based on text files and other wide-spread formats (.gz, .json).
  * Includes a README file in each data directory.
  * Includes a copy of the measurement script, if possible.

.. note::
  Nevertheless, you should *always* read in the data using
  pdata.analysis.dataview, which provides plenty of useful functions for
  automatically parsing data not just from the tabular data stored with
  add_points(), but also the instrument parameters stored in the JSON
  files. Because of the latter, it is highly recommended to use dataview
  as a preparser even if you use something else than Python for further
  analysis.

Concretely, a data directory contains the following files:

  * :file:`tabular_data.dat` -- Point added with add_points().
  * :file:`snapshot.json` -- Instrument parameter snapshot when begin() was called.
  * :file:`snapshot.row-<n>.diff<m>.json` -- (json)diff of parameter changes, recorded when the there were <n> data rows in tabular_dat.dat. <m> is a simple counter, in case multiple diffs are created for the same row.
  * :file:`log.txt` -- copy of messages from the logging module.
  * A copy of the Jupyter notebook (.ipynb) or other measurement
    script, if possible.

  Optionally, the files may be compressed (.gz or .tar.gz).

.. note:: A downside of the chosen data format is that it's relatively
  slow to read from disk to memory. So if you are dealing with larger
  data sets, it's highly recommended to split your analysis script
  into multiple steps and make use of caching parsed values and/or
  intermediate analysis results in cache files. There are several easy
  ways of doing that in Python, for example using `pickle
  <https://docs.python.org/3/library/pickle.html>`_ or `json
  <https://docs.python.org/3/library/json.html>`_

Content in this manual
----------------------------

.. toctree::
    :maxdepth: 2

    Overview <self>
    install
    api
    contributing
