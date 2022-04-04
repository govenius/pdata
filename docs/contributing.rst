Contributing
============

Contributions of all kinds are welcome, preferably through github.


Core code
---------

Some principles that should help keep the system simple and
maintainable in the long term:

* Options should be explicit, rather than \*args or \*kwargs, when
  possible.  We will also raise loud warnings (or exceptions) if we
  are not sure what the user wants.

Testing
-------

Currently pdata includes very limited automated testing (see
:file:`test` subdirectory). Contributions adding tests are highly
welcome.
