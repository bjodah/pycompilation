pycompilation
=============

.. image:: https://travis-ci.org/bjodah/pycompilation.png?branch=master
   :target: https://travis-ci.org/bjodah/pycompilation


pycompilation bundles python convenience classes and functions for performing compilation
and linking on the fly from python. Developed to simplify working with code-generation,
compilation and import (meta-programming) from Python.

Installation
------------
Example using pip (modify to your own needs):

::

   $ python3 -m pip install --user pycompilation


Examples
--------
Look at ``examples/*_main.py`` which show how pycompilation can be used.

You may also look at other projects which uses pycompilation:

- pycodeexport_
- cInterpol_ 
- finitediff_ 
- symvarsub_

.. _pycodeexport: http://github.com/bjodah/pycodeexport
.. _cInterpol: http://github.com/bjodah/cinterpol
.. _finitediff: http://github.com/bjodah/finitediff
.. _symvarsub: http://github.com/bjodah/symvarsub

Documentation
-------------
You find the latest documentation at http://pycompilation.readthedocs.org/


Dependencies
------------
For the examples to work you need:

- Cython
- A C compiler (e.g. gcc)
- A C++ compiler (e.g. g++)
- A Fortran complier (e.g. gfortran)
- appdirs (python module)

License
-------
Open Source. Released under the very permissive simplified (2-clause) BSD license. 
See LICENSE for further details.

TODO
----

 - Windows support
 - PGI compilers
 - Better Intel MKL linkline help (cf. "Intel® Math Kernel Library Link Line Advisor")
