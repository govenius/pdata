'''
Joonas Govenius, 2019-2022

Short miscellaneous helpers.
'''

from pdata._metadata import __version__

import json
import warnings
import numpy as np
import numbers
import collections
from typing import Any

def preprocess_snapshot(snap, delete_timestamps=True, convert_ndarrays=False):
  '''
  Helper that preprocesses snapshots so that they are compatible with pdata/jsondiff.
  In particular converts numpy arrays to regular Python lists, if requested.
  Also, optionally, deletes QCodes timestamp entries from a snapshot dict,
  i.e. dict entries of the form "ts": <str>.
  '''

  def preprocesss_dict(d):
    ''' Recursive helper. '''
    for k in get_keys(d):
      if isinstance(d[k], (collections.abc.Mapping, collections.abc.Sequence)) and not isinstance(d[k], str):
        preprocesss_dict(d[k])
      elif convert_ndarrays and isinstance(d[k], np.ndarray):
        # jsondiff doesn't handle ndarrays by default, but the custom
        # PdataJSONDiffer below does, so this conversion is no longer
        # needed and is disabled by default.
        d[k] = d[k].tolist()
      elif delete_timestamps and k=="ts" and isinstance(d[k], str):
        del d[k] # QCodes updates these very often

  preprocesss_dict(snap)
  return snap

def get_keys(d, reject_str=True, reject_ndarray=True):
  """Return keys of d, if d is dict-like, or indices if d is
     list-like. Raise TypeError for str/ndarray if reject_str/ndarray
     is True.
  """
  if not isinstance(d, (collections.abc.Mapping, collections.abc.Sequence)): raise TypeError()
  if reject_str and isinstance(d, str): raise TypeError()
  if reject_ndarray and isinstance(d, np.ndarray): raise TypeError()
  try: return list(d.keys()) # Assume that d is dict-like
  except AttributeError: return list(range(0,len(d))) # Assume that d is a list, tuple, or similar

from jsondiff import JsonDiffer
class PdataJSONDiffer(JsonDiffer):
  """Custom JSON diff creator that handles Numpy ndarrays and lists of
     only scalars as complete blocks. That is, does not create diffs
     at element level within ndarrays. This is much faster than the
     default jsondiff list diff creation, and becomes important if the
     snapshots contain e.g. AWG patterns that can be long vectors.
  """

  def _obj_diff(self, a, b):

    if a is b: return self.options.syntax.emit_value_diff(a, b, 1.0), 1.0

    def is_vector(x): return isinstance(x, (list,tuple)) and all(np.isscalar(xi) for xi in x)

    # Check whether a or b is an ndarray or a list of only scalars.
    a_is_ndarray = isinstance(a, np.ndarray)
    b_is_ndarray = isinstance(b, np.ndarray)
    if a_is_ndarray or b_is_ndarray or is_vector(a) or is_vector(b):

      if np.array_equal(a,b): return self.options.syntax.emit_value_diff(a, b, 1.0), 1.0 # The ndarrays/lists are equal

      # Otherwise they differ, emit a diff for the complete
      # ndarray/list, instead of drilling down to element level diffs.
      return self.options.syntax.emit_value_diff(a.tolist() if a_is_ndarray else a,
                                                 b.tolist() if b_is_ndarray else b, 0.0), 0.0

    # Otherwise process as usual.
    return super()._obj_diff(a, b)

class NumpyJSONEncoder(json.JSONEncoder):
    """This JSON encoder adds support for serializing types that the built-in
    ``json`` module does not support out-of-the-box. See the docstring of the
    ``default`` method for the description of all conversions.

    This is taken straight from QCoDeS:
    https://github.com/QCoDeS/Qcodes/blob/master/qcodes/utils/helpers.py

    QCoDeS is available under the MIT open-source license :

      Permission is hereby granted, free of charge, to any person
      obtaining a copy of this software and associated documentation
      files (the "Software"), to deal in the Software without
      restriction, including without limitation the rights to use,
      copy, modify, merge, publish, distribute, sublicense, and/or
      sell copies of the Software, and to permit persons to whom the
      Software is furnished to do so, subject to the following
      conditions:

      The above copyright notice and this permission notice shall be
      included in all copies or substantial portions of the Software.

      SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
      EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
      OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
      NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
      HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
      WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
      FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
      OTHER DEALINGS IN THE SOFTWARE.

    """

    def default(self, obj: Any) -> Any:
        """
        List of conversions that this encoder performs:
        * ``numpy.generic`` (all integer, floating, and other types) gets
          converted to its python equivalent using its ``item`` method (see
          ``numpy`` docs for more information,
          https://docs.scipy.org/doc/numpy/reference/arrays.scalars.html).
        * ``numpy.ndarray`` gets converted to python list using its ``tolist``
          method.
        * Complex number (a number that conforms to ``numbers.Complex`` ABC) gets
          converted to a dictionary with fields ``re`` and ``im`` containing floating
          numbers for the real and imaginary parts respectively, and a field
          ``__dtype__`` containing value ``complex``.
        * Numbers with uncertainties  (numbers that conforms to ``uncertainties.UFloat``) get
          converted to a dictionary with fields ``nominal_value`` and ``std_dev`` containing floating
          numbers for the nominal and uncertainty parts respectively, and a field
          ``__dtype__`` containing value ``UFloat``.
        * Object with a ``_JSONEncoder`` method get converted the return value of
          that method.
        * Objects which support the pickle protocol get converted using the
          data provided by that protocol.
        * Other objects which cannot be serialized get converted to their
          string representation (using the ``str`` function).
        """
        with warnings.catch_warnings():
            # this context manager can be removed when uncertainties
            # no longer triggers deprecation warnings
            warnings.simplefilter("ignore", category=DeprecationWarning)
            import uncertainties

        if isinstance(obj, np.generic) \
                and not isinstance(obj, np.complexfloating):
            # for numpy scalars
            return obj.item()
        elif isinstance(obj, np.ndarray):
            # for numpy arrays
            return obj.tolist()
        elif (isinstance(obj, numbers.Complex) and
              not isinstance(obj, numbers.Real)):
            return {
                '__dtype__': 'complex',
                're': float(obj.real),
                'im': float(obj.imag)
            }
        elif isinstance(obj, uncertainties.UFloat):
            return {
                '__dtype__': 'UFloat',
                'nominal_value': float(obj.nominal_value),
                'std_dev': float(obj.std_dev)
            }
        elif hasattr(obj, '_JSONEncoder'):
            # Use object's custom JSON encoder
            jsosencode = getattr(obj, "_JSONEncoder")
            return jsosencode()
        else:
            try:
                s = super().default(obj)
            except TypeError:
                # json does not support dumping UserDict but
                # we can dump the dict stored internally in the
                # UserDict
                if isinstance(obj, collections.UserDict):
                    return obj.data
                # See if the object supports the pickle protocol.
                # If so, we should be able to use that to serialize.
                if hasattr(obj, '__getnewargs__'):
                    return {
                        '__class__': type(obj).__name__,
                        '__args__': getattr(obj, "__getnewargs__")()
                    }
                else:
                    # we cannot convert the object to JSON, just take a string
                    s = str(obj)
            return s
