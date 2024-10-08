.. pdata documentation master file, created by sphinx-quickstart
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


pdata: Straightforward and robust data storage for experimental data
====================================================================

This *procedural* data storage package provides a self-contained
interface **focused exclusively on storing and reading experimental
data**, using an approach **independent of the specific measurement
framework used for instrument control**.

The main goals are to provide an interface that:

  * Automatically stores a lot of metadata, including parameters that change during a measurement.
  * Is *procedural* rather than *functional* in terms of the API the experimenter sees, as procedural programming tends to be easier to understand for a typical experimental physicist.
  * Uses standard Python flow-control constructs (for, while, if, etc.) for looping over setpoints.
  * The API aims to be self-explanatory, wherever possible.

In practice, the experimenter starts by defining the columns for a
traditional table of data points, and then calls an explicit
:code:`add_points(<new data points>)` to add rows to the table,
typically inside a few nested for loops that loop over setpoints. In
the background, **pdata automatically records all changes to
instrument parameters** each time :code:`add_points` is called.

On the analysis side, the main functionality of pdata is to provide
correct implementations for reading the traditional data table,
concatenating multiple data sets, as well as **parsing the
automatically stored instrument parameters** (with :code:`dataview`
and :code:`add_virtual_dimension()`).

Pdata also provides basic helpers for quick data visualization (with
:code:`basic_plot()`), graphical dataset selection (with
:code:`data_selector()`), and live plotting (with
:code:`monitor_dir()`).

Pdata does *not* aim to be a fully-featured plotting and analysis
library. Instead, we implement **easy-to-use export capabilities of
parsed data to other Python and non-Python tools** (see
:ref:`Analyzing with other tools <analyzing_with_other_tools>`).

Below you find a short guide to using the most important features of
pdata. You can find the same content in an interactive Jupyter
notebook format under the :code:`examples` directory. For more
detailed documentation of each function, see the :doc:`API page
</api>`

.. note:: The only requirement for the framework used to control the
          instruments is that the framework needs to be able to return
          instrument parameters as a python dict object. Or more
          specifically, a dict compatible with `json
          <https://docs.python.org/3/library/json.html>`_ and
          `jsondiff <https://pypi.org/project/jsondiff/>`_. In `QCoDeS
          <https://github.com/QCoDeS/Qcodes>`_ for example, you would
          use :code:`qcodes.station.Station.default.snapshot()`.

.. contents:: Basic usage
    :local:
    :depth: 2

Saving data in measurement script
---------------------------------

Under the :code:`examples` directory,
you find an example of running a measurement using `QCoDeS
<https://github.com/QCoDeS/Qcodes>`_ for instrument control, while using pdata
for data storage and regular Python for flow control (for loops, etc.).

The essential part of running the measurement is::

  # Define a function that gets the current instrument settings from QCoDeS (as a dict)
  import qcodes.station
  get_qcodes_instrument_snapshot = lambda s=qcodes.station.Station.default: s.snapshot(update=True)

  from pdata.procedural_data import run_measurement

  # Columns are specified as (<name>, <unit>), or just <name> if the quantity is dimensionless.
  with run_measurement(get_qcodes_instrument_snapshot,
                       columns = [("frequency", "Hz"),
                                  "S21"],
                       name='power-sweep', # <-- arbitrary str descriptive of measurement type
                       data_base_dir=data_root) as m:

    logging.warning('This test warning will (also) end up in log.txt within the data dir.')

    data_path = m.path()
    logging.warning(f'Data directory path = {m.path()}.')

    for p in [-30, -20, -10]:
      vna.power(p) # <-- note that this new value gets automatically stored in the data
      freqs, s21 = vna.acquire_S21()
      m.add_points({'frequency': freqs, 'S21': s21})


.. note:: By default, floats and complex numbers are serialized to
          strings with 16 significant figures, corresponding to the
          precision of 64-bit floats. Other data types are converted
          to string by calling :code:`str()`, and replacing tabs and
          new lines with spaces. The default serializers and data
          types are inferred from the data types in the first data row
          passed to :code:`add_points()`. You can override the
          defaults for any column with a column specification like
          this: :code:`(<column name>, <unit>, <formatter>, <dtype>)`,
          where :code:`<formatter>` is a single-argument function that
          converts the argument to a string (e.g.  :code:`lambda x:
          f"{x:.3e}"` if you wanted to optimize the file size).
          :code:`<dtype>` is an optional data type class that is
          stored in the tabular data header as metadata, and later
          helps parse the data correctly.

Interrupting a measurement prematurely
--------------------------------------

You can call :code:`pdata.procedural_data.abort_measurements()` from any other Python
kernel running on the same machine to controllably abort all ongoing
measurements on the machine, after their next call to
:code:`add_points()`.

.. warning:: *Do not interrupt a measurement by restarting the Python
  kernel*. This can lead to sporadic and difficult-to-debug
  communication issues in case the kernel was in the middle of
  communicating with an external measurement instrument. The external
  instrument can be left waiting for an answer it never gets.

Reading data in analysis scripts
--------------------------------

Here is how you read the data back from the above example using DataView::

  from pdata.analysis.dataview import DataView, PDataSingle

  # Read the data from disk into a PDataSingle object
  # and then feed that into a DataView object for analysis
  #
  # PDataSingle and Dataview are separate because you can
  # concatenate multiple data dirs into one DataView by
  # adding multiple PDataSingle's to the array below.
  d = DataView([ PDataSingle(data_path), ])

That will read the data table including all of the columns given as
arguments to :code:`run_measurement()`. In addition, **we can add any
instrument setting as a virtual dimension** that looks for the rest of
the analysis just like any other column in the data table::

  d.add_virtual_dimension('VNA power', # <-- name of the new column
                          from_set=('instruments', 'vna',
                                    'parameters', 'power', 'value'))

.. note:: The path given in the :code:`from_set` argument depends on
          the framework you use for instrument control. You can
          determine it using the graphical helper
          :code:`dataexplorer.snapshot_explorer(d)`, or by manually
          examining :code:`d.settings()[0][1]` or snapshot.json.gz.

If you're using Jupyter, take a look at the HTML-formatted summary of
the parsed data, by typing :code:`d` in a new cell.

Often, you would next use :code:`basic_plot` to plot the data using a
one-liner, or :ref:`export the parsed data
<analyzing_with_other_tools>` to e.g. xarray for more involved
analysis. But here, for pedagogical purposes, let's first take a more
verbose approach to see what :code:`DataView` can do.

Let's run some print statements to see how to access the data columns::

  print('Instruments in the snapshot file:')
  print(d.settings()[0][1]['instruments'].keys())

  # You can now access the columns by name:
  print('\nFirst few frequencies: %s' % (d["frequency"][:5]))
  print('First few powers: %s' % (d["VNA power"][:5]))

  print('\nUnique powers in the data set: %s' % (np.unique(d["VNA power"])))

  print('\nSweeps based on a per-sweep-fixed parameter: %s' % d.divide_into_sweeps('VNA power'))

  print('\nSweeps based on a per-sweep-swept parameter: %s' % d.divide_into_sweeps('frequency'))

Which outputs the following::

  Instruments in the snapshot file:
  dict_keys(['vna'])

  First few frequencies: [5.900e+09 5.905e+09 5.910e+09 5.915e+09 5.920e+09]
  First few powers: [-30. -30. -30. -30. -30.]

  Unique powers in the data set: [-30. -20. -10.]

  Sweeps based on a per-sweep-fixed parameter: [slice(0, 41, None), slice(41, 82, None), slice(82, 123, None)]

  Sweeps based on a per-sweep-swept parameter: [slice(0, 41, None), slice(41, 82, None), slice(82, 123, None)]

Let's next divide the data into sweeps with
:code:`divide_into_sweeps`. We can then plot those sweeps with
matplotlib, as an example::

  import matplotlib.pyplot as plt
  fig, ax = plt.subplots()

  for dd in d.sweeps('frequency'): # <-- split data rows into monotonously increasing/decreasing sweeps
    power = dd.single_valued_parameter('VNA power')
    ax.plot(dd['frequency'], dd['S21'], label="%s dBm" % power)

  ax.set(xlabel='f (Hz)', ylabel='S21')
  ax.set_yscale('log')
  ax.legend();

.. image:: ./_static/index_S21-example_manual.png
   :alt: S21 vs frequency
   :scale: 80 %

.. _analyzing_with_other_tools:

Analyzing with other tools (xarray, pandas, Matlab, etc.)
---------------------------------------------------------

After you've used DataView to parse the data, you can easily export
it, including virtual dimensions, to several other tools.

A convience function for conversion to `xarray
<https://docs.xarray.dev/en/stable/index.html>`_ is included::

  # Assuming the DataView d from example above:
  xa = d.to_xarray("S21", coords=[ "frequency", "VNA power" ])

.. note:: Xarray is well-suited for N-dimensional parameter/coordinate
          sweeps that were executed with nested for loops in which the
          looped coordinate values in each loop were selected mostly
          independent of other coordinates. More precisely, xarray
          will be an efficient representation if the measured
          coordinates (x,y,...,z) span most of X⊗Y...⊗Z, where X (Y)
          [Z] is a set of all unique x (y) [z] found in the data set.
          Otherwise there will be lots of empty values in the xarray,
          which are filled with :code:`fill_value` (:code:`np.nan` by
          default).

.. note:: Usually, you'll want to use setpoints, rather than measured
          values, as coordinates in an xarray. If a coordinate
          :code:`c` is instead a measured value, you probably want to
          specify coarse graining with :code:`coarse_graining={c:
          <Delta>}`, which causes coordinates differing by at most
          :code:`<Delta>` to be interpreted as the same coordinate.

.. note:: Note that if the same coordinate combination is repeated
          more than once in the data set, only the last measured value
          will appear in the output xarray. If you want to preserve
          information about repetitions, add another coordinate for
          the repetition number.

.. note:: Spaces, dashes and other special characters in coordinate
          names are replaced automatically by underscores, as these
          don't work well with xarray syntax.

Converting a DataView object :code:`d` to a `Pandas
<https://pandas.pydata.org/>`_ data frame::

  import pandas # Assumes you've installed pandas
  dataframe = pandas.DataFrame({col: d[col] for col in d.dimensions()})

You could further convert the Pandas dataframe to a CSV file, which
can be read by many languages::

  dataframe.to_csv("outputdata.csv")

If you want to work with Matlab, you can use `savemat()
<https://docs.scipy.org/doc/scipy/reference/generated/scipy.io.savemat.html>`_::

  from scipy.io import savemat # Assumes you've installed scipy
  savemat("outputdata.mat", {col: d[col] for col in d.dimensions()})

Data explorer
-------------

There are some helpers in :code:`pdata.analysis.dataexplorer` for
quick visualization of data sets.

Interactive data set selector
*****************************

You can use :code:`data_selector` in a Jupyter notebook to create an
interactive element for easily selecting data sets from a given
directory::

  sel = dataexplorer.data_selector(data_root)
  display(sel)

.. image:: ./_static/index_dataset-selector.png
   :alt: interactive data set selector
   :scale: 100 %

Basic plots (one liners)
************************

You can combine the interactive selector above with
:code:`basic_plot`, in a separate Jupyter notebook cell, to actually
generate a plot of S21 vs frequency for the selected data sets::

  dataexplorer.basic_plot(data_root, sel.value, "frequency", "S21", ylog=True)

That will already create a plot similar to the above manually created
one, but to also add VNA power in the legend, you can add a
:code:`preprocessor`. In this example, the preprocessor adds VNA power
as a virtual dimensions so that it can be used as a
:code:`slowcoordinate` for the plot::

  def add_vdims(dd):
    dd.add_virtual_dimension('VNA power', units="dBm",
                              from_set=('instruments', 'vna',
                                        'parameters', 'power', 'value'))
    return dd

  dataexplorer.basic_plot(data_root, sel.value,
                          "frequency", "S21",
                          slowcoordinate="VNA power",
                          ylog=True,
                          preprocessor=add_vdims)

.. image:: ./_static/index_S21-example_dataexplorer.png
   :alt: S21 vs frequency, produced with data explorer
   :scale: 80 %

Live plotting
*************

:code:`monitor_dir` can be used to create the same plot as above. The
difference is that we don't manually select the data sets. Instead the
plot will keep updating with new data, until you send an interrupt
signal to the kernel::

  # Plot data directories that were modified < 600 s ago,
  # and include "power-sweep" in the directory name.
  # The cell runs indefinitely, until an interrupt is sent to the Python kernel.
  dataexplorer.monitor_dir(data_root, name_filter="power-sweep", age_filter=600,
			  x="frequency", y="S21", ylog=True,
			  slowcoordinate="VNA power",
			  preprocessor=add_vdims);

.. note:: By default, :code:`monitor_dir` uses :code:`data_selector`
          for choosing which data directories to plot, and
          :code:`basic_plot` for plotting them. You can, however,
          override them by specifying custom :code:`selector` and
          :code:`plotter` arguments to :code:`monitor_dir`, for easy
          creation of arbitrarily complex live plots. The custom
          functions just need to take the same arguments as
          :code:`data_selector` and :code:`basic_plot` do.

Content in the rest of this manual
----------------------------------

.. toctree::
    :maxdepth: 2

    Basic usage <self>
    speed
    install
    dataformat
    api
    contributing
