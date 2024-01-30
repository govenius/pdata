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

Getting started/Full documentation
----------------------------------

See the `documentation <http://pdata.readthedocs.io>`_ at RTD for
instructions on getting started.
