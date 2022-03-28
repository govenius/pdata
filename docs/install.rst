Installation
============

Get the latest version from `qithub
<https://github.com/govenius/pdata>`_, make sure you have the
:ref:`required packages <requirements>` installed, and run::

  pip install .

.. _requirements:

Requirements
------------

Besides the measurement framework you plan to use (e.g., `QCoDeS
<https://github.com/QCoDeS/Qcodes>`_), you need:

  * `NumPy <http://www.numpy.org/>`_
  * `jsondiff <https://pypi.org/project/jsondiff/>`_
  * `pytz <https://pypi.org/project/pytz/>`_
  *  `requests <https://pypi.org/project/requests/>`_, `ipykernel <https://pypi.org/project/ipykernel/>`_, `ipython <https://pypi.org/project/ipython/>`_, `notebook <https://pypi.org/project/notebook/>`_ (for storing .ipynb measurement scripts)
  * `ipywidgets <https://ipywidgets.readthedocs.io/en/latest/>`_ (for dataexplorer)
  * `matplotlib <https://matplotlib.org/>`_ (for dataexplorer)
  * `Setuptools <https://setuptools.readthedocs.io/en/latest/>`_ (for installation)

You are probably using a `Conda environment
<https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html>`_,
or some other way of managing the package dependencies for your
broader measurement framework, so make sure those packages are in that
environment.
