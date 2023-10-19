###########################
# User-configurable options
###########################

# If you don't have a C++ compiler installed, you may want to disable
# the fast_parser extension as a work around. On Linux it's usually
# trivial to install one but on Windows it requires a bit more
# effort. See
# https://cython.readthedocs.io/en/latest/src/quickstart/install.html
# for more information.
FAST_PARSER_ENABLED = True

# You can keep this as True if you didn't make any changes relevant to
# the fast_parser extension. It removes the risk that your version of
# Cython generates something different from what's been tested.
USE_PREGENERATED_C_SOURCES = True

###########################

from setuptools import setup
from setuptools.extension import Extension
import numpy

# Most input to setup(...) comes from setup.cfg, but Cython
# dependencies are specified here (probably more elegant ways exist).

if USE_PREGENERATED_C_SOURCES:
  cythonize = lambda x: x # i.e. do nothing
else:
  from Cython.Build import cythonize

ext_modules = []

if FAST_PARSER_ENABLED:
  ext_modules.append(Extension(
        "pdata.analysis.fast_parser.tabular_data_parser",
        [f"pdata/analysis/fast_parser/tabular_data_parser.{'cpp' if USE_PREGENERATED_C_SOURCES else 'pyx'}"],
        include_dirs=[numpy.get_include()],
        #libraries=['somelib', ...],
        #library_dirs=['/some/path/to/include/'],
        language="c++"
    ))

setup(ext_modules=cythonize(ext_modules))
