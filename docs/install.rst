Installation
============

It's easiest to install pdata from the `conda-forge
<https://conda-forge.org/docs/user/introduction.html>`_ channel using
`Conda <https://docs.conda.io/>`_.

For example, you can create a new conda environment including pdata,
`QCoDeS <https://qcodes.github.io/Qcodes/start/index.html>`_, and
`JupyterLab <https://jupyter.org/>`_ like this::

  conda create -n pdatasandbox --channel conda-forge pdata qcodes jupyterlab

Here, :code:`pdatasandbox` is an arbitrary name for the new
environment. If needed, familiarize yourself with the basics of `Conda
environments
<https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html>`_.

You can also activate the `conda-forge channel
<https://conda-forge.org/docs/user/introduction.html>`_ for an
existing environment or all environments::

  conda config --add channels conda-forge # Add --env if you want this only for the currently active conda environment
  conda config --set channel_priority strict # --env

After which you can run (inside the appropriate conda environment)::

  conda install pdata

Often, however, it's simpler and more robust to create a new conda
environment and specify all the required packages in one go in the
:code:`create` command, as in the :code:`pdatasandbox` example
above. In general, you should consider conda environments disposable.

pip install
-----------

If you're not using Conda, download the latest version from `qithub
<https://github.com/govenius/pdata>`_ and install with pip. That is,
run this in the root folder where :file:`setup.cfg` is::

  pip install .

Note that you also `need a C++ compiler
<https://cython.readthedocs.io/en/latest/src/quickstart/install.html>`_.
Alternatively, you can disable :code:`fast_parser` by setting
:code:`FAST_PARSER_ENABLED=False` in :code:`setup.py`.

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
  * `Cython <https://cython.readthedocs.io/>`_ (if you modify fast_parser)
