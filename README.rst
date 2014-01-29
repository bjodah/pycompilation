=============
pycompilation
=============

.. image:: https://travis-ci.org/bjodah/pycompilation.png?branch=master
   :target: https://travis-ci.org/bjodah/pycompilation

pycompilation bundles python convenience classes and functions for performing compilation
and linking on the fly from python. Developed with code-generation, compilation and
import (meta-programming) of math related problems using the SymPy package in mind.

Installation
============
Example using pip (modify to your own needs):

    1. ``pip install --user --upgrade -r https://raw.github.com/bjodah/pycompilation/master/requirements.txt``
    2. ``pip install --user --upgrade https://github.com/bjodah/pycompilation/archive/v0.2.16.tar.gz``


Templating
==========

Mako comes highly recommended as a template engine. For easier usage, a convenience method is provided in ``pycompilation.util``.
The Code classes in ``pycompilation.codeexport`` use this too.


License
=======
Open Source. Released under the very permissive simplified (2-clause) BSD license. 
See LICENSE.txt for further details.

Examples
========
Look at ``examples/*_main.py`` which show how pycompilation can be used.

You may also look at other projects which uses pycompilation:

 - cInterpol_ 
 - finitediff_ 
 - symvarsub_

.. _cInterpol: http://github.com/bjodah/cinterpol
.. _finitediff: http://github.com/bjodah/finitediff
.. _symvarsub: http://github.com/bjodah/symvarsub

TODO
====

 - Windows support
 - PGI compilers
 - Better Intel MKL linkline help (cf. "Intel® Math Kernel Library Link Line Advisor")
