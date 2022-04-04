Installation
============

If you are using `Conda <https://docs.conda.io/>`_, the easiest way to
install pdata is to activate the `conda-forge channel
<https://conda-forge.org/docs/user/introduction.html>`_::

  conda config --add channels conda-forge # Add --env if you want this only for the currently active conda environment
  conda config --set channel_priority strict # --env

After which you can simply run::

  conda install pdata

Incidentally, you can also install `QCoDeS
<https://qcodes.github.io/Qcodes/start/index.html>`_ from conda-forge.

If you're not familiar with Conda already, familiarize yourself with
`Conda environments
<https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html>`_.

If you're not use Conda, get the latest version from `qithub
<https://github.com/govenius/pdata>`_, make sure you have the
:ref:`required packages <requirements>`, and run::

  pip install .

.. _requirements:

Requirements
------------

  * `NumPy <http://www.numpy.org/>`_
  * `jsondiff <https://pypi.org/project/jsondiff/>`_
  * `pytz <https://pypi.org/project/pytz/>`_
  *  `requests <https://pypi.org/project/requests/>`_, `ipykernel <https://pypi.org/project/ipykernel/>`_, `ipython <https://pypi.org/project/ipython/>`_, `notebook <https://pypi.org/project/notebook/>`_ (for storing .ipynb measurement scripts)
  * `ipywidgets <https://ipywidgets.readthedocs.io/en/latest/>`_ (for dataexplorer)
  * `matplotlib <https://matplotlib.org/>`_ (for dataexplorer)
  * `Setuptools <https://setuptools.readthedocs.io/en/latest/>`_ (for installation)
