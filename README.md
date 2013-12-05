pycompilation
=========

pycompilation bundles python convenience classes and function for performing compilation
and linking on the fly from python. Developed with codegeneration, compilation and
import (meta-programming) of math related problems using the SymPy package.

# Templating

Mako comes highly recommended as template engine and a convenience method is provided in helpers:
`render_template_to(...)` which makes use of template files convenient for code generation.

# License
Open Soucrce. Released under the very permissive simplified (2-clause) BSD license. See LICENCE.tx for further details.

# Examples

InvNewton still has some minor bug: 
``` python invnewton_main.py -y x/(x+1) -o 1 -l 3 --sample-N 500 ```


# TODO
Remove extra_options... it's just confusing..
