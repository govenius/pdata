from setuptools import setup
from setuptools.extension import Extension
from Cython.Build import cythonize
import numpy

# Most input comes from setup.cfg, but Cython dependencies are
# specified here (probably more elegant ways exist).
setup(ext_modules=cythonize([
    Extension(
        "pdata.analysis.fast_parser.tabular_data_parser",
        ["pdata/analysis/fast_parser/tabular_data_parser.pyx"],
        include_dirs=[numpy.get_include()],
        #libraries=['somelib', ...],
        #library_dirs=['/some/path/to/include/'],
        language="c++"
    ),
  ]))
