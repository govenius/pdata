pdata: Simple-to-understand and robust data storage for experimental data
=========================================================================

This procedural data storage package provides a self-contained
interface for storing experimental data using an approach that is
independent from intricasies of broader measurement frameworks. The
main goals are to provide an interface that is:
  * Maximizes the amount of automatically stored metadata, both at the
    start of a measurement but also changes to parameters **during** the
    measurement.
  * "Procedural" rather than "functional" in terms of the API the
    experimenter sees, as procedural programming tends to be easier to
    understand for a typical experimental physicist who is not a
    thoroughly trained programmer.
  * The API aims to be self-explanatory, wherever possible.

In practice, this means that pdata has an explicit add_points(<new
data points>) function that adds new points. In addition pdata saves a
diff of instrument parameters each time add_points() is called.

The goal of the data format is to be self-documenting, such that it is
possible to figure out what it is, even without the pdata source or
binary package. Therefore the data format is:
  * Relatively verbose (i.e. **not** optimized for size).
  * Based on text files and other wide-spread formats (.gz, .json).
  * Includes a README file in each data directory.
  * Includes a copy of the measurement script, if possible.

Nevertheless, you should *always* read in the data using
pdata.analysis.dataview, which provides plenty of useful functions for
automatically parsing data not just from the tabular data stored with
add_points(), but also the instrument parameters stored in the JSON
files. Because of the latter, it is highly recommended to use dataview
as a preparser even if you use something else than Python for further
analysis.

See the `documentation <http://pdata.readthedocs.io>`_ at RTD (or the
`docs subdirectory <docs>`_) for instructions on getting started.
