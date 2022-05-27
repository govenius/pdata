Contributing
============

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
