=============
pycompilation
=============

.. image:: https://travis-ci.org/bjodah/pycompilation.png?branch=master
   :target: https://travis-ci.org/bjodah/pycompilation

pycompilation bundles python convenience classes and functions for performing compilation
and linking on the fly from python. Developed with code-generation, compilation and
import (meta-programming) of math related problems using the SymPy package in mind.

Templating
==========

Mako comes highly recommended as a template engine. For easier usage, a convenience method is provided in ``pycompilation.util``:
``render_template_to(...)``

License
=======
Open Soucrce. Released under the very permissive simplified (2-clause) BSD license. See LICENSE.tx for further details.

Examples
========
All files named *_main.py in examples/ show how pycompilation can be used.
You may also look at other projects which uses pycompilation:
    - [cInterpol](http://github.com/bjodag/cinterpol)
    - [finitediff](http://github.com/bjodag/finitediff)
    - [symvarsub](http://github.com/bjodag/symvarsub)

TODO
====
    - Windows support
    - PGI compilers
    - Better Intel MKL linkline help (cf. "Intel® Math Kernel Library Link Line Advisor")
