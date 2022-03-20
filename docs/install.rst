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
  * `Setuptools <https://setuptools.readthedocs.io/en/latest/>`_

You are probably using a `Conda environment
<https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html>`_,
or some other way of managing the package dependencies for your
broader measurement framework, so make sure those packages are in that
environment.

If not, in Ubuntu 20.04 you can do::

  sudo apt-get install python3-numpy python3-jsondiff python3-setuptools
