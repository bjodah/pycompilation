#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This example illustrates how caching of both results, code and binaries
can be achieved using joblib and pycompilation. The cachedir location
is chosen using appdirs package.
"""


from __future__ import (absolute_import, division, print_function)

import argh
import numpy as np

from cached_code import MyPoly


def main(coeffs="10,0,1", diff=0, xmin=0, xmax=3, N=4, clean=False):
    """
    Compile a native callback of a polynomial
    """
    coeffs = tuple(map(float, coeffs.split(',')))

    poly = MyPoly(coeffs)

    # 1. Do heavy work that generates python object
    #    representation convertible to code
    Dpoly = poly.diff(diff)

    # 2. Compile and link code, import module
    mod = Dpoly.compile_link_import_py_ext()

    # 3. Compute results
    x = np.linspace(xmin, xmax, N)
    result = mod.callback(x)

    # 4. Check results.
    for _ in range(diff, 0, -1):
        coeffs = tuple((p*c for p, c in enumerate(coeffs[1:], 1)))
    ref = np.zeros_like(x)
    for p, c in enumerate(coeffs):
        ref += c*x**p
    assert np.allclose(result, ref)

    if clean:
        poly.memory.clear()
        Dpoly.memory.clear()
    return result

if __name__ == '__main__':
    argh.dispatch_command(main)
