# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cpow=True
# cython: c_string_type=bytes
# cython: c_string_encoding=ascii
# distutils: language = c++
"""Functions for reading contents of tabular_data.dat files quickly.

Floating point numbers are parsed using fast_float.h. See
https://github.com/fastfloat/fast_float/ and Daniel Lemire, Number
Parsing at a Gigabyte per Second, Software: Practice and Experience 51
(8), 2021, arXiv:2101.11408.
"""

from libcpp.string cimport string

cdef extern from "<system_error>" namespace "std":
  enum class errc:
    illegal_byte_sequence
    protocol_error
    protocol_not_supported
    wrong_protocol_type

cdef extern from *:
    """
    // Don't know how else to invoke the default constructor for an enum class from Cython,
    // so use this verbatim-docstring-include-trick to define a function that does it.
    std::errc getSuccessErrc() { return std::errc(); }

    // Also define a way of getting a string representation of an
    // error (even though this wouldn't be too hard with Cython syntax
    // either).
    std::string getErrcMessage(std::errc e) { return make_error_code(e).message(); }
    """
    errc getSuccessErrc()
    string getErrcMessage(errc e)

cdef extern from "fast_float.h" namespace "fast_float":
  ctypedef struct from_chars_result:
    const char* ptr
    errc ec

  from_chars_result from_chars(const char* first, const char* last, double& value)


import cython

from cython.view cimport array as cvarray
import numpy as np
cimport numpy as cnp

from libc.stdint cimport uint8_t
from libcpp.vector cimport vector

cdef enum ColumnType:
  double_col, longlong_col, complex_col, char_col

cdef struct ColumnSpec:
  ColumnType col_type
  void* output_buffer # <-- type depends on col_type

cdef inline from_chars_result parse_longlong(const char* p, long long* outInt) noexcept:
  """ Parse a 64-bit integer from ASCII string p and store it in outInt.
      Returns a pointer to the termination byte, or null if parsing
      fails. Any byte other than '0'...'9' is an acceptable
      termination byte. Leading zeros accepted, leading whitespace is
      not."""

  # Define character literals like this because I don't know how else
  # to define them in Cython without ending up with Python
  # interaction.  For example, b"0"[0] seems to produce a lot of
  # Python code. Or maybe it would be later optimized away anyway...?
  #
  # These should be const but I don't know how to do that either in
  # Cython. Presumably the C++ compiler will figure it out anyway.
  cdef uint8_t CHAR_ZERO = <uint8_t> 48
  cdef uint8_t CHAR_MINUS = <uint8_t> 45
  cdef uint8_t CHAR_PLUS = <uint8_t> 43

  cdef const char* start = p

  cdef bint negative = False
  cdef long long norm = 0
  cdef uint8_t c = (<uint8_t> p[0]) - CHAR_ZERO  #b'0'[0]

  # Check for - or +
  if c == <uint8_t> (CHAR_MINUS-CHAR_ZERO):
    negative = True
    p += 1; c = (<uint8_t> p[0]) - CHAR_ZERO
  elif c == <uint8_t> (CHAR_PLUS-CHAR_ZERO):
    p += 1; c = (<uint8_t> p[0]) - CHAR_ZERO

  if c > 9: return from_chars_result(start, errc.illegal_byte_sequence) # No digits found

  # Read digits
  while c < 10:
    norm = 10*norm + c
    p += 1; c = (<uint8_t> p[0]) - CHAR_ZERO

  if negative:
    outInt[0] = -norm
  else:
    outInt[0] =  norm

  return from_chars_result(p, getSuccessErrc())

cdef inline from_chars_result parse_single_value(const char* p, const char* start_of_block, const char* end_of_block,
                                                 ColumnSpec col_spec, size_t row):
  cdef double* double_buf
  cdef long long* longlong_buf

  cdef char CHAR_TAB = <char> 9
  cdef char CHAR_NEWLINE = <char> 10
  cdef char CHAR_CARRRET = <char> 13
  cdef char CHAR_PLUS = <char> 43
  cdef char CHAR_j = <char> 106

  cdef from_chars_result r

  if col_spec.col_type == ColumnType.double_col:
    double_buf = <double*> (col_spec.output_buffer)
    return from_chars(p, end_of_block, double_buf[row])

  elif col_spec.col_type == ColumnType.longlong_col:
    longlong_buf = <long long*> (col_spec.output_buffer)
    return parse_longlong(p, &longlong_buf[row])

  elif col_spec.col_type == ColumnType.complex_col:
    double_buf = <double*> (col_spec.output_buffer)

    # Parse (presumably) real part
    r = from_chars(p, end_of_block, double_buf[2*row])
    if r.ec != getSuccessErrc(): return r

    # Special cases:
    if r.ptr[0]==CHAR_j: # Real part is (implicitly) zero (e.g. "1.23e4j")
      double_buf[2*row+1] = double_buf[2*row]
      double_buf[2*row] = 0.
      r.ptr += 1
      return r

    while r.ptr[0]==CHAR_CARRRET: r.ptr += 1 # In case line ends in \r\n
    if r.ptr[0]==CHAR_TAB or r.ptr[0]==CHAR_NEWLINE: # Imag part is (implicitly) zero (e.g. "1.23e4")
      double_buf[2*row+1] = 0.
      return r

    # Parse imaginary part
    if r.ptr[0]==CHAR_PLUS: r.ptr += 1 # skip leading +
    r = from_chars(r.ptr, end_of_block, double_buf[2*row + 1])
    if r.ec != getSuccessErrc() or r.ptr[0] != CHAR_j: return r # Expected j at the end of a complex number
    r.ptr += 1 # Skip j

    return r

  elif col_spec.col_type == ColumnType.char_col:
    longlong_buf = <long long*> (col_spec.output_buffer)

    longlong_buf[2*row] = p-start_of_block # index of start of value, relative to input block
    while p<end_of_block and p[0]!=CHAR_NEWLINE and p[0]!=CHAR_TAB: p += 1
    longlong_buf[2*row+1] = p-start_of_block # index of end of string, relative to input block

    # Strip possible \r at the end, in case the line ends in \r\n
    if p-1 >= start_of_block and (p-1)[0]==CHAR_CARRRET: longlong_buf[2*row+1] -= 1

    return from_chars_result(p, getSuccessErrc())

cdef from_chars_result parse_up_to_max_rows(bytes block, size_t max_rows, const vector[ColumnSpec] col_specs, size_t &outNrows, ptrdiff_t &parsed_bytes):
  """ Parse at most max_rows data rows from block. Returns the number of
      processed bytes. Number of parsed rows is stored in outNrows. """
  cdef size_t L = len(block)
  cdef const char* start = block
  cdef const char* end_of_block = start+L
  cdef size_t row = 0
  cdef size_t col
  cdef size_t ncols = col_specs.size()

  cdef char CHAR_TAB = <char> 9
  cdef char CHAR_NEWLINE = <char> 10
  cdef char CHAR_CARRRET = <char> 13
  cdef char CHAR_HASH = <char> 35

  cdef errc success = getSuccessErrc()

  cdef from_chars_result r = from_chars_result(start, success)

  while r.ptr < end_of_block and row < max_rows:

    while r.ptr[0]==CHAR_CARRRET: r.ptr += 1 # In case line ends in \r\n
    if r.ptr[0] == CHAR_NEWLINE: # skip empty lines
      r.ptr += 1
      continue

    if r.ptr[0] == CHAR_HASH: # skip comment lines
      while r.ptr < end_of_block and r.ptr[0] != CHAR_NEWLINE: r.ptr += 1
      continue

    # Parse all but last column
    for col in range(ncols-1):
      r = parse_single_value(r.ptr, start, end_of_block, col_specs[col], row)
      if r.ec != success: break
      if r.ptr[0] != CHAR_TAB: r = from_chars_result(r.ptr, errc.protocol_error); break # Expected a tab as column separator
      r.ptr += 1

    # Parse last column
    r = parse_single_value(r.ptr, start, end_of_block, col_specs[ncols-1], row)
    if r.ec != success: break
    while r.ptr[0]==CHAR_CARRRET: r.ptr += 1 # In case line ends in \r\n
    if r.ptr[0] != CHAR_NEWLINE: r = from_chars_result(r.ptr, errc.protocol_not_supported); break # Expected a new line to indicate the end of a row
    r.ptr += 1

    row += 1

  outNrows = row
  parsed_bytes = r.ptr - start if r.ptr!=NULL else -1
  return r

cdef inline double [:] getDoubleView(cnp.ndarray np_buf):
  """ This is a workaround for creating a memory view inside a for loop. """
  cdef double[::1] v = np_buf
  return v

cdef inline long long [:] getLonglongView(cnp.ndarray np_buf):
  """ This is a workaround for creating a memory view inside a for loop. """
  cdef long long[::1] v = np_buf
  return v

def parse_tabular_data(s, dtypes, chunk_size=1000000):
  """Parse tabular data contained in a byte string s, containing columns
     with data types given by dtypes.

     chunk_size controls the size of the internal buffer used to store
     parsed results in a single iteration.  Using a number that is
     equal to or slightly larger than the real number of data rows is
     optimal. Using a larger chunk size wastes some memory. Using a
     smaller chunk size introduces a small performance penalty since
     values from each chunk need to be copied into a single buffer at
     the end. In most cases, neither one is a big issue.

  """
  # Map various float and int subtypes to float and int
  for i in range(len(dtypes)):
    if dtypes[i] in [ np.float64, np.float32, np.float16 ]: dtypes[i] = float
    if dtypes[i] in [ np.int64, np.int32, np.int16, np.int8, np.intc ]: dtypes[i] = int
    if dtypes[i] in [ np.complex128, np.complex64, np.cdouble ]: dtypes[i] = complex

  assert all(dt in [ float, int, complex, str ] for dt in dtypes ), f"One or more unsupported datatypes: {dtypes}"

  # Parse first chunk
  parsed_bytes, data = parse_up_to_chunk_size(s, dtypes, chunk_size)
  if parsed_bytes == len(s): return data

  # Data didn't fit into a single chunk --> Read more chunks. Could
  # do this in C++ but there's little benefit as long as chunk_size is
  # reasonably large.
  chunks = [ data ]
  prev_parsed_bytes = parsed_bytes
  while prev_parsed_bytes < len(s)-1:
    parsed_bytes, data = parse_up_to_chunk_size(s[prev_parsed_bytes:], dtypes, chunk_size)
    assert parsed_bytes != 0, "parse_up_to_chunk_size() didn't parse anything"

    chunks.append(data)
    prev_parsed_bytes += parsed_bytes

  assert prev_parsed_bytes == len(s), f'Input not fully parsed. chunk_size={chunk_size}, parsed_bytes={parsed_bytes}'

  # For each column, concatenate values from all chunks into a single array
  return dict( (col,
                np.concatenate( [ ch[col] for ch in chunks ] )
                ) for col in data.keys() )

def parse_up_to_chunk_size(s, dtypes, chunk_size):

  # Allocate output buffers
  output_buffers = [ np.empty(chunk_size*(2 if dtp==complex or dtp==str else 1),
                              dtype={float: np.double, int: np.longlong, complex: np.double, str:np.intp}[dtp])
                     for dtp in dtypes ]

  cdef vector[ColumnSpec] col_specs

  for dt,np_buf in zip(dtypes, output_buffers):

    # This should always be the case for 1D buffers from np.empty(), but double check just in case
    assert np_buf.flags['C_CONTIGUOUS'], "The parser assumes that output buffers are contiguous in memory."

    if   dt==float:
      col_specs.push_back(
        ColumnSpec(ColumnType.double_col, &(getDoubleView(np_buf)[0]))
        )
    elif dt==complex:
      col_specs.push_back(
        ColumnSpec(ColumnType.complex_col, &(getDoubleView(np_buf)[0]))
        )
    elif dt==int:
      col_specs.push_back(
        ColumnSpec(ColumnType.longlong_col, &(getLonglongView(np_buf)[0]))
        )
    elif dt==str:
      col_specs.push_back(
        ColumnSpec(ColumnType.char_col, &(getLonglongView(np_buf)[0]))
        )

  cdef size_t n_parsed_rows = 0
  cdef ptrdiff_t parsed_bytes = 0
  cdef const char* start = s
  cdef from_chars_result r = parse_up_to_max_rows(start, chunk_size, col_specs, n_parsed_rows, parsed_bytes)

  # Sanity checks and error handling
  if r.ec != getSuccessErrc():
    if parsed_bytes >= 0:
      print(f"Parsing error near character {parsed_bytes}: {s[parsed_bytes:min(len(s), parsed_bytes+30)]}")

    error_code = r.ec
    try:
      error_message = getErrcMessage(r.ec)
      error_message_bytes= <bytes> error_message
      assert False, (f"Got error code {error_code} ({error_message_bytes}) from parse_up_to_max_rows()")
    finally:
      del error_message

  # Postprocess certain dtypes
  for j in range(len(output_buffers)):
    if dtypes[j] == complex:
      # Reinterpret complex numbers, which are parsed above as two doubles
      output_buffers[j] = output_buffers[j][:2*n_parsed_rows].view(np.cdouble)

    if dtypes[j] == str:
      # Copy strings to new Python str objects. They are parsed above as
      # start and end pointers, within the original input string s.
      b = output_buffers[j]
      output_buffers[j] = np.array([
          s[b[2*k]:b[2*k+1]].decode('utf-8')
        for k in range(n_parsed_rows)], dtype=object)

  # output_buffers now contain the parsed values.
  # Strip the uninitialized rows beyond n_parsed_rows.
  # Give the columns names "col<i>", as expected by PDataSingle/DataView.
  return parsed_bytes, dict( (f"col{j}", np_buf[:n_parsed_rows]) for j,np_buf in enumerate(output_buffers) )
