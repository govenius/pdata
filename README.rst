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

In practice, the experimenter calls an explicit :code:`add_points(<new
data points>)` function to add rows to a traditional table of data
points, with user-defined columns. In the background, **pdata
automatically records all changes to instrument parameters** each
time :code:`add_points` is called.

In addition, pdata provides useful helpers for reading back the data,
including automatically recorded instrument parameters, basic helpers
for visualization, and good export capabilities to other tools for
further analysis.

Getting started/Full documentation
----------------------------------

See the `documentation <http://pdata.readthedocs.io>`_ at RTD for
instructions on getting started.
