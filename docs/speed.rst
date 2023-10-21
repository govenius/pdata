Speed considerations
====================

The script :code:`test/time_it.py` contains some rudimentary timing
tests. You can run it yourself or check out the :ref:`time_it.py
example` below.

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
