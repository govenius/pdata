Contributing and licences
=========================

Contributions of all kinds are welcome, preferably as pull requests
through Github.


Core code
---------

Some principles that should help keep the system simple and
maintainable in the long term:

* Options should be explicit, rather than \*args or \*kwargs, when
  possible.
* We raise loud warnings (or exceptions) if we are not sure what the
  user wants.

Testing
-------

pdata includes basic integration tests that verify high-level
functionality (see :file:`test/run_tests.py`). **Please run these
tests whenever you create a commit/pull request**, to double check
that you did not accidentally break something::

  cd test
  python run_tests.py

Ideally, pull requests addressing bugs would include a new regression
test that fails (passes) before (after) your fix.

**Contributions adding automated tests of any kind are highly
welcome!**


Licenses
--------

pdata code is licensed under the MIT license (see :file:`LICENSE`),
with the following exceptions:

* :file:`pdata/static/style.css` and
  :file:`pdata/static/dataview-template.html` contain CSS and HTML
  from `xarray <https://docs.xarray.dev/en/stable/index.html>`_, which
  is licensed under Apache License Version 2.0 (see
  :file:`pdata/static/XARRAY_LICENSE`).
* xarray in turn uses :file:`pdata/static/icons-svg-inline.html`,
  which has IcoMoon icons licensed under CC BY 4.0 (see
  :file:`pdata/static/ICOMOON_LICENSE`).
