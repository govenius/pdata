Speed considerations
====================

The script :code:`test/time_it.py` contains some rudimentary timing
tests. You can run it yourself or check out the :ref:`time_it.py
example` below.

fast_parser
-----------

The custom C++ :code:`pdata.analysis.fast_parser` **module improves
read speed by almost an order of magnitude**, compared to versions
prior to `pdata v2.7.0
<https://github.com/govenius/pdata/releases/tag/v2.1.0>`_. It relies
largely on `fast_float <https://github.com/fastfloat/fast_float/>`_.

The :code:`fast_parser` module is used by default as long as:

  * `pdata v2.7.0 <https://github.com/govenius/pdata/releases/tag/v2.1.0>`_ or newer is used, and
  * all the columns are of type :code:`float`, :code:`int`, :code:`complex` or :code:`str`, and
  * :code:`pdata.analysis.dataview.FAST_PARSER_ENABLED` is true. You can set this to false at runtime if you want to disable :code:`fast_parser`.

Otherwise, `numpy.genfromtxt
<https://numpy.org/doc/stable/reference/generated/numpy.genfromtxt.html>`_
is used.

Optimizing number of significant figures
----------------------------------------

By default, floats and complex numbers are serialized to strings with
16 significant figures, corresponding to the precision of 64-bit
floats. This is usually overkill. Both speed and dataset size can be
improved by providing a custom formatter when passing the column
definition :code:`(<column name>, <unit>, <formatter>, <dtype>)` to
:code:`run_measurement`.

For example, if the values you're storing originate from a 10 or 12
bit ADC, you could safely store just four significant figures by using
:code:`(<column name>, <unit>, lambda x: f"{x:.3e})`

Another example: If the values you're storing originate from a digital
voltmeter with 10 µV resolution, you could use :code:`(<column name>,
'muV', str, int)` and store the values in microvolts. In principle,
you could use 10 uV as units, but it would be less clear and would
provide very little extra performance gain.


.. warning:: Accidentally storing too few significant figures can be
             extremely annoying if you only notice the problem once
             it's no longer easy to remeasure. Therefore, you should
             generally not optimize the number of significant figures
             if your data sets are small anyway. It's also a good idea
             to include at least one or two extra digits beyond what
             you think you need.


time_it.py example
------------------

Results using pdata v2.1.1 and a bottom-shelf laptop (Intel Pentium
N3700 @ 1.60GHz)::

  Adding 1M 2-column rows, with format=None and compress=False...
  26.328 s per repetition.
  Reading it to PDataSingle using fast_parser...
    0.489 s per repetition.
  Converting it to DataView...
    1.582 s per repetition.
  Reading it to PDataSingle using np.genfromtxt...
    9.002 s per repetition.
  Converting it to DataView...
    1.649 s per repetition.

  Adding 1M 2-column rows, with format=None and compress=True...
    45.482 s per repetition.
  Reading it to PDataSingle using fast_parser...
    1.110 s per repetition.
  Converting it to DataView...
    1.638 s per repetition.
  Reading it to PDataSingle using np.genfromtxt...
    9.481 s per repetition.
  Converting it to DataView...
    1.649 s per repetition.

  Adding 1M 2-column rows, with format=lambda x: "%.4e"%x and compress=False...
    19.176 s per repetition.
  Reading it to PDataSingle using fast_parser...
    0.326 s per repetition.
  Converting it to DataView...
    1.589 s per repetition.
  Reading it to PDataSingle using np.genfromtxt...
    7.504 s per repetition.
  Converting it to DataView...
    1.669 s per repetition.

  Adding 1M 2-column rows, with format=lambda x: "%.4e"%x and compress=True...
    31.987 s per repetition.
  Reading it to PDataSingle using fast_parser...
    0.565 s per repetition.
  Converting it to DataView...
    1.617 s per repetition.
  Reading it to PDataSingle using np.genfromtxt...
    7.535 s per repetition.
  Converting it to DataView...
    1.580 s per repetition.
