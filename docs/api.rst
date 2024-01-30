API
===

Almost all of the measurement-side functionality is implemented in
procedural_data.py, and the :code:`Measurement` class within it.

Analysis side functionality is implemented in dataview.py and
dataexplorer.py.

:ref:`genindex`

.. :ref:`modindex`
.. :ref:`search`


Measurement
---------------

procedural_data
+++++++++++++++

.. automodule:: pdata.procedural_data

.. autofunction:: run_measurement

.. autofunction:: abort_measurements

.. autoclass:: Measurement
    :members:


Analysis
---------------

dataexplorer
++++++++++++

.. automodule:: pdata.analysis.dataexplorer
    :members:

DataView
++++++++

.. automodule:: pdata.analysis.dataview

.. autoclass:: DataView
    :members:

.. autoclass:: PDataSingle
    :members:
