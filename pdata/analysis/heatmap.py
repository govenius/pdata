import logging
import numpy as np
import xarray

def heatmap(traces, slowvals, min_col_width=None):
  """Given a list of y vs x traces specified as a list of (xvals, yvals)
     tuples, and corresponding slow axis values, generate a
     heatmap with x on the horizontal, slow value on the vertical
     axis and y as a pixel value (= color).

     maxcols specifies the maximum number of pixels in the horizontal direction.
  """
  # Sort the traces by slow value
  new_order = np.argsort(slowvals)
  slowvals = np.array(slowvals)[new_order]
  traces = np.array(traces)[new_order]

  x, img = resample_onto_regular_grid(traces, dx_min=min_col_width)

  # x and slowvalues give the centers of the pixels.
  # Also calculate the edge locations too:
  edges = [ center_coordinates_to_edges(coords)
            for coords in (x, slowvals) ]

  return { "img": img,
           "horizontal_axis": x, "vertical_axis": slowvals,
           "horizontal_axis_edges": edges[0], "vertical_axis_edges": edges[1] }


def resample_onto_regular_grid(traces, dx_min=None):
  """Given a list of y vs x traces specified as a list of (xvals, yvals)
     tuples, resample all traces onto a common evenly-spaced x axis
     that is dense enough to contain values close to the original x
     values.

     If dx_min is specified, the common x axis won't have a spacer
     denser than that.

     Returns common_x_axis, <no. of traces> x <len(common_x_axis)>
     array of resampled y values.
  """
  assert all(t.shape[0]==2 for t in traces), "traces should have shape equal to 2 x <n points>"
  traces = [ t.transpose() for t in traces ]

  # Range of x in all traces:
  x_min = min( t[:,0].min() for t in traces )
  x_max = max( t[:,0].max() for t in traces )

  # Smallest increment in any trace
  dx = min( smallest_division(t[:,0]) for t in traces )
  if not np.isfinite(dx):
    # This should only happen if all traces have just a single point.
    logging.warning('Could not figure out the horizontal spacing dx (%s?). Using dx = 1.', dx)
    dx = 1.

  # A complex x coordinate doesn't make a lot of sense in principle,
  # but if all the imaginary parts are zero, then assume that it's
  # just a dtype issue (which happens in particular if y is complex).
  if np.iscomplexobj(x_min) or np.iscomplexobj(x_max) or np.iscomplexobj(dx):
    assert not np.iscomplex(x_min), "x has a nonzero imaginary part"
    assert not np.iscomplex(x_max), "x has a nonzero imaginary part"
    assert not np.iscomplex(dx), "x has a nonzero imaginary part"
    x_min = np.real(x_min); x_max = np.real(x_max); dx = np.real(dx)

  if dx_min is not None: dx = max(dx, dx_min)

  # Use dx as the fundamental pixel width in the "image" containing all traces.
  # Figure out how many columns that implies.
  ncols = 1 + int(np.ceil( (x_max - x_min) / dx ))

  # Allocate the "image" matrix for storing all traces.
  img = np.zeros((len(traces), ncols), dtype=float) + np.nan
  logging.debug(f'Output image size = {img.shape}. x = arange({x_min}, {x_max}, {dx})')

  # Fill it with the nearest value (in x) for each pixel.
  # Leave parts outside the domain of each trace as np.nan
  for i,t in enumerate(traces):
    sorted_trace = t[ np.real(t[:,0]).argsort() ] # required by interp
    first_col = int(np.round((sorted_trace[0,0] - x_min)/dx))
    cols_in_trace = int(1 + np.real(sorted_trace[-1,0] - sorted_trace[0,0])/dx)

    if cols_in_trace == 1:
      img[i,first_col] = sorted_trace[:,1]
    else:
      img[i,first_col:first_col+cols_in_trace] = interp1d(
        np.real(sorted_trace[0,0]) + dx*np.arange(cols_in_trace),
        np.real(sorted_trace[:,0]), sorted_trace[:,1])

  horizontal_axis_vals = ( x_min + dx*np.arange(ncols) )

  return horizontal_axis_vals, img

def center_coordinates_to_edges(x):
  """Given a list of 1D pixel coordinates, return the corresponding
     pixel edge coordinates.
  """
  edges = np.zeros(len(x) + 1) + np.nan
  dx = np.diff(x) if len(x)>1 else 1.
  edges[0] = x[0] - dx[0]/2 # <-- leftmost edge
  edges[1:-1] = x[:-1] + dx/2 # <-- all the right edges, except the last one
  edges[-1] = x[-1] + dx[-1]/2 # <-- rightmost edge
  return edges

def smallest_division(xvals):
  """Figure out the smallest division dx in a list of (potentially unsorted) x values"""
  tracex = xvals.copy()
  tracex.sort()
  m = ~np.isnan(tracex)
  if len(tracex[m]) < 2: return np.inf
  a = np.diff(tracex[m])
  if len(a[a>0]) < 1: return np.inf
  return a[a>0].min()

def interp1d(x, xp, fp):
  """Mimic scipy.interpolate.interp1d(xp, fp, kind="nearest")(x).

     This is so far the only scipy function needed in pdata, and also
     interp1d is marked as "legacy", so not adding the scipy
     dependency (or not yet at least).
  """
  result = np.zeros(len(x)) + np.nan
  within_bounds = (x >= xp.min()) * (x <= xp.max())
  if within_bounds.max() == False: return result
  result[within_bounds] = fp[np.abs(
    x[within_bounds] - np.broadcast_to(xp, (within_bounds.sum(), len(xp))).transpose()
  ).argmin(axis=1)]
  return result
