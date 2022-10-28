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

If you're not using Conda, download the latest version from `qithub
<https://github.com/govenius/pdata>`_ and install with pip. That is,
run this in the root folder where :file:`setup.cfg` is::

  pip install .

.. _requirements:

Requirements
------------

Required packages are listed in :file:`setup.cfg`. Here are some of them:

  * `NumPy <http://www.numpy.org/>`_
  * `jsondiff <https://pypi.org/project/jsondiff/>`_
  * `pytz <https://pypi.org/project/pytz/>`_
  * `uncertainties <https://pythonhosted.org/uncertainties/>`_
  *  `requests <https://pypi.org/project/requests/>`_, `ipykernel <https://pypi.org/project/ipykernel/>`_, `ipython <https://pypi.org/project/ipython/>`_, `notebook <https://pypi.org/project/notebook/>`_, `ipylab <https://github.com/jtpio/ipylab>`_ (for storing .ipynb measurement scripts)
  * `ipywidgets <https://ipywidgets.readthedocs.io/en/latest/>`_ (for dataexplorer)
  * `matplotlib <https://matplotlib.org/>`_ (for dataexplorer)
  * `Setuptools <https://setuptools.readthedocs.io/en/latest/>`_ (for installation)
