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

InvNewton still has bugs (try changing to -0.7 and it works): 
``` python -m pudb invnewton_main.py -y 'tan(x)' -l 5 -o 3 --sample-N 1000 --x-lo -0.8 --x-hi 1.0 ```

# TODO

