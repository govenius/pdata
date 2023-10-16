On-disk data format
===================

Introduction
------------

As a user of pdata, you don't normally need to worry about the on-disk
data format, since you should be using :code:`pdata.analysis.dataview`
for loading the data. This page is meant mainly for developers of
pdata itself, and other people who run into unexpected issues and need
some understanding of the inner workings of the package.

.. warning:: Despite the format being self-explanatory in principle,
  you should **always read in the data using**
  :code:`pdata.analysis.dataview`, which provides plenty of useful
  functions for automatically parsing data not just from the tabular
  data stored with :code:`add_points`, but also the instrument
  parameters stored in the JSON files. Reimplementing these features
  is essentially never a wise use of time. You can use
  :code:`pdata.analysis.dataview` for the initial parsing step even if
  you use other tools later on in the analysis (see :ref:`Analyzing
  with other tools <analyzing_with_other_tools>`).

.. contents:: Contents
    :local:
    :depth: 3

Specification
-------------

Each pdata data set is stored in its own directory. The directory
contains the following files.

tabular_data.dat
++++++++++++++++
    
Data table with rows added using :code:`add_points`, and columns
defined as arguments of :code:`run_measurement`. Only ASCII
characters are allowed, and new lines are encoded as :code:`\n`.

Any row starting with :code:`#` is a comment row. A row is considered
empty if it contains only white space or the :code:`#` character and
white space. All characters except :code:`\n` are allowed.

All non-empty non-comment rows are data rows. Each data row contains a
single data point as a tab-separated (:code:`\t`) list of values, one
value per column. The tab-separated values can contain any character
except :code:`#`, :code:`\t`, or :code:`\n`. :code:`add_points` will
automatically replace these characters with spaces.

Numerical values must not include extra whitespace at the beginning or
end. Numerical values must not contain a leading plus
sign. Floating-point numbers must be in the locale-independent format
expected by the C++17 from_chars function. In particular, use a period
(:code:`.`) as the decimal separator and no thousands separator.

Complex numbers must be formatted as <float0>+<float1>j, or
<float0>-<|float1|>j if float1 is negative. Both real and imaginary
parts must be present.

The last non-empty comment row contains the column names and units as
a tab-separated (:code:`\t`) list of strings. Each string is of the
format (:code:`<column name> (<units>)`), where the column names
(units) must match the regular expression :code:`[\w\d\s\-+%=/*&]+`
(:code:`[\w\d\s\-+%=/*&]*`).

All comment rows preceding the first data row are called the
header. All comment rows after the last data row are defined as the
footer.

The header contains a version number for the ondisk format, encoded as
:code:`# ondisk_format_version = <major>.<minor>.<patch>`, following
`Semantic Versioning <https://semver.org/>`_. *New in ondisk format
version 1.0.0.*

The header contains the version numbers of the pdata, jsondiff, and
numpy packages as well as the version of Python, encoded as
:code:`# <package>_version = <major>.<minor>.<patch>`. *New in ondisk
format version 1.0.0.*

The header contains the column data types, encoded as a tab-separated
(:code:`\t`) list of strings. Each string has the format
:code:`<module>.<dtype>`, where :code:`<module>` is typically either
:code:`<numpy>` or :code:`<builtins>`. These help
:code:`pdata.analysis.dataview` parse common dtypes (float, int,
complex, str, etc.) back into the correct type. *New in ondisk format
version 1.0.0.*

The header (footer) contains a timestamp specifying when the
measurement started (ended), encoded as :code:`# Measurement started
(ended) at <timestamp>`, where timestamps has the format
:code:`%Y-%m-%d %H:%M:%S.%f`. *New in ondisk format version 1.0.0.*

The footer contains a list of snapshot diff rows, encoded as :code:`#
Snapshot diffs preceding rows (0-based index): <row no>, <another row
no>, ...`, where row numbers are defined in the same way as in the
:code:`snapshot.row-<n>.diff<m>.json` filenames (see below). These are
intended to provide a consistency check, and are available only after
the measurement has ended. *New in ondisk format version 1.0.0.*

Optionally, this file may be compressed (.gz added to file name).

snapshot.json
+++++++++++++

Instrument parameter snapshot when :code:`run_measurement` started,
encoded as a JSON file loadable with the `json
<https://docs.python.org/3/library/json.html>`_ module, using the
standard decoder.

Optionally, this file may be compressed (.gz added to file name).

snapshot.row-<n>.diff<m>.json
+++++++++++++++++++++++++++++

`jsondiff <https://pypi.org/project/jsondiff/>`_ of parameter changes,
recorded when there were <n> data rows in tabular_data.dat. <m> is a
simple counter, in case multiple diffs are created for the same row.

The diffs are always in the :code:`compact` format. *TODO:* No clear
specification of the format seems to exist. Let's specify it here.

Optionally, these files may be combined and compressed into a gzipped
tarball (tar.gz added to file name).

log.txt
+++++++

A copy of log messages recorded during the measurement (from the logging module).

A copy of the Jupyter notebook (.ipynb) or other measurement script
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

A copy of the main measurement script is stored if possible.


Motivation for the chosen format
--------------------------------

Pdata is geared toward single-lab-scale experimental physics
experiments, such as superconducting qubit experiments, IV
measurements, etc. This is in contrast to big-data experiments
(e.g. collecting machine learning data sets).

An important goal of the data format is to be self-documenting, such
that it is in principle straightforward for a competent programmer to
figure out how to parse the data, even without the pdata source.

The format also aims to be stable enough that the latest version of
:code:`pdata.analysis.dataview` is able to read any data set recorded
with any previous version of pdata.

Another important design criterion is that it must be
possible to read the latest data in a separate analysis script
(i.e. separate process) as soon as new data becomes available from the
experiment.

Therefore the data format is:

  * Stream-like, i.e. the on-disk data set is a valid and up-to-date dataset at all times during an on-going experiment, and not only after the measurement ends.
  * Relatively verbose. Or conversely, optimizing file size or speed is **not** a top priority.
  * Based on text files and other wide-spread formats (.gz, .json).
  * Includes a README file in each data directory.
  * Includes a copy of the measurement script, if possible.

.. note:: An advantage of using gzipped files, besides the obvious
  benefit of smaller file size, is that gzipped files contain a
  checksum. This ensures that (post-measurement) data corruption does
  not go unnoticed.

.. note:: A downside of the chosen data format is that it's relatively
  slow to read from disk to memory. So if you are dealing with larger
  data sets, it's highly recommended to split your analysis script
  into multiple steps and make use of caching parsed values and/or
  intermediate analysis results in cache files. There are several easy
  ways of doing that in Python, for example using `pickle
  <https://docs.python.org/3/library/pickle.html>`_, numpy, or `json
  <https://docs.python.org/3/library/json.html>`_.

Discussion on alternative formats
---------------------------------

Here we have some notes on alternative formats, *which are not used by
pdata*.

To simplify the task of having :code:`pdata.analysis.dataview` support
all pdata datasets, including ones recorded with earlier versions of
pdata, **changes to the on-disk data format are generally to be
avoided** without very good reason.

Text based vs binary
++++++++++++++++++++

Binary formats could offer better write and read speeds, assuming that
implementation details are properly tuned. Reaching hardware-limited
speed is, however, almost irrelevant for the vast majority of physics
experiments that pdata is geared toward.

Binary *cache* files are also easy to create in Python and can be
integrated as part of the data analysis workflow in most cases. Such
cache files can (and should) be considered disposable, so they can be
native to the system and can therefore provide unbeatable speed.

In general, any binary format is more opaque than a text-based format,
if you were faced with the challenge of reverse engineering the
format. With very wide spread formats this is less of a concern
(e.g. .npy/.npz).

Numpy .npy/.npz
+++++++++++++++

Numpy .npy/.npz would be a very reasonable binary format for the data
rows of tabular data. The format is `well-specified and stable
<https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html#module-numpy.lib.format>`_
and has a design philosophy similar to pdata's, except that it's
binary.

HDF5
++++

The main argument against using HDF5 is that the HDF5 specification is
very complex (see `100+ page HDF5 specification
<https://docs.hdfgroup.org/hdf5/develop/_f_m_t3.html>`_ vs `.npy/.npz
specification
<https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html#module-numpy.lib.format>`_),
without providing any clear advantage compared to .npz, in the case of
pdata. The complexity of the specification isn't a problem from the
point of view of routine use since one, and only one, `HDF5 library
implementation <https://github.com/hdfgroup/hdf5>`_ exists. However,
it could be non-trivial to debug issues in the unlikely event that
bugs related to the HDF5 library would be encountered.

.. note:: At first sight it seems tempting to encode snapshots as
  nested HDF5 groups, which would provide strong data typing. However,
  the overhead in file size is severe (~kB per group!).

Binary JSON
+++++++++++

There are a few variants of JSON-like formats but with binary
encoding. These would potentially offer faster read speeds, while also
being rather simple. This could be a benefit in use cases with very
large snapshot diffs

The main disadvantage is that there are several slightly-incompatible
variants of these formats and none of them seems broadly adopted,
although `Mathematica supports UBJSON
<https://reference.wolfram.com/language/workflow/GenerateJSON.html>`_.
