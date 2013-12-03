#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, division, absolute_import, unicode_literals

import argh
import logging
import os
import shutil

import numpy as np
import matplotlib.pyplot as plt
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

from pycompilation import pyx2obj
from pycompilation.codeexport import C_Code, ArrayifyGroup, DummyGroup

from cInterpol import interpolate_by_finite_diff, PiecewisePolynomial

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__file__)


def make_solver(y, x, ylim, xlim):
    """
    Essentially this does what our invnewton_template.c will
    do, (we need to solve iteratively using newtons method to
    populate the lookup table used in the C routine).
    """
    try:
        from symvarsub.numtransform import lambdify
    except IOError:
        from sympy.utilities.lambdify import lambdify

    cb_y = lambdify(x, y)
    cb_dydx = lambdify(x, y.diff(x))

    y0 = ylim[0]
    DxDy = (xlim[1]-xlim[0])/(ylim[1]-ylim[0])
    def inv_y(y, abstol=1e-12, itermax=10, conv=None):
        """
        Returns x and error estimate thereof
        """
        x_ = y0+y*DxDy # guess
        dy = cb_y(x_)-y
        i=0
        dx=0.0 # could skip while-loop
        while abs(dy) > abstol and i < itermax:
            dx = -dy/cb_dydx(x_)
            x_ += dx
            dy = cb_y(x_)-y
            i += 1
            if conv != None: conv.append(dx)
        if i==itermax:
            raise RuntimeError("Did not converge")
        return x_, abs(dx)

    return inv_y



def ensure_monotonic(y, x, xlim=None, strict=False):
    """
    Checks whehter an expression (y) in one variable (x)
    is monotonic.

    Arguments:
    -`y`: expression for the dependent variable in x
    -`x`: independent variable
    -`xlim`: optional limitation on the span in x for which to check monotonicity
    -`strict`: flag to check for strict monotonicity (dydx != 0), default: False

    Returns a length 4 tuple:
     (Bool for monotonic: True/False,
      Tuple of two (sorted) ylims: (ylim0, ylim1)
      Bool for increasing: True/False,
      )
    """
    ylim = map(float, (y.subs({x: xlim[0]}),
                       y.subs({x: xlim[1]}))
    )
    if ylim[0] > ylim[1]:
        ylim = (ylim[1], ylim[0])
        incr = False
    elif ylim[0] == ylim[1]:
        return False, None, None
    else:
        incr = True

    dydx = y.diff(x)
    d2ydx2 = dydx.diff(x)
    xs = sympy.solve(dydx, x)
    for v in xs:
        if xlim:
            if v < xlim[0] or v > xlim[1]: continue
        if strict: return False, None, None
        if d2ydx2.subs({x: v}) != 0:
            return False, None, None
    return True, ylim, incr


class InvNewtonCode(C_Code):
    templates = ['invnewton_template.c']
    copy_files = ['invnewton_wrapper.o'] # cythonized and compiled .pyx <-- already put inplace
    source_files = ['invnewton.c']
    obj_files = ['invnewton.o', # rendenered and compiled template
                 'invnewton_wrapper.o']
    so_file = 'invnewton_wrapper.so'

    compilation_options = C_Code.compilation_options + ['fast', 'openmp', 'c99']

    def __init__(self, yexpr, lookup_N, order, xlim,
                 x, **kwargs):
        self.monotonic, self.ylim, self.incr = ensure_monotonic(yexpr, x, xlim)
        if not self.monotonic:
            raise ValueError("{} is not monotonic on xlim={}".format(yexpr, xlim))
        self.y = yexpr
        self.dydx = yexpr.diff(x)
        self.lookup_N = lookup_N
        self.order = order
        self.xlim = xlim
        self.x = x
        self.populate_lookup_x()
        super(InvNewtonCode, self).__init__(**kwargs)

    def populate_lookup_x(self):
        self.lookup_x = np.empty(self.lookup_N*(self.order+1))
        data = np.empty((self.lookup_N, (self.order+1)/2))
        # The lookup is equidistant in y (implicit problem!)
        self.lookup_y = np.linspace(self.ylim[0], self.ylim[1], self.lookup_N)
        # First find our x's for the equidistant y's
        yspace = (self.ylim[1]-self.ylim[0])/(self.lookup_N-1)
        solve_x = make_solver(self.y, self.x, self.ylim, self.xlim)
        for i in range(self.lookup_N):
            nsample = self.order*2-1
            xsample = np.empty(nsample)
            if i == 0:
                ysample = np.linspace(self.lookup_y[i],
                                      self.lookup_y[i]+yspace,
                                      nsample)
            if i == self.lookup_N-1:
                ysample = np.linspace(self.lookup_y[i]-yspace,
                                      self.lookup_y[i],
                                      nsample)
            else:
                ysample = np.linspace(self.lookup_y[i]-yspace/2,
                                      self.lookup_y[i]+yspace/2,
                                      nsample)
            for j, y in np.ndenumerate(ysample):
                val, err = solve_x(ysample[j])
                assert err < (self.xlim[1]-self.xlim[0])/self.lookup_N/1e3
                xsample[j] = val
            data[i,:] = interpolate_by_finite_diff(
                ysample, xsample, self.lookup_y[i], (self.order-1)/2)

        pw = PiecewisePolynomial(self.lookup_y, data)
        self.lookup_x[:] = np.array(pw.c).flatten()

    def variables(self):
        cses, (y_in_cse, dydx_in_cse) = self.get_cse_code(
            [self.y, self.dydx])
        c = [sympy.Symbol('c_' + str(o), real = True) for \
             o in range(self.order + 1)]
        dummy_groups = (DummyGroup('coeffdummy', c),)
        # See approx_x() in invnewton_template.c
        arrayify_groups=(ArrayifyGroup('coeffdummy', 'lookup_x', 'tbl_offset'),)
        localy = sympy.Symbol('localy')
        poly_expr = self.as_arrayified_code(
            sum([c[o]*localy**o for o in range(self.order + 1)]),
            dummy_groups, arrayify_groups)
        return {
            'ylim': self.ylim,
            'xlim': self.xlim,
            'lookup_N': self.lookup_N,
            'lookup_x': self.lookup_x,
            'poly_expr': poly_expr,
            'order': self.order,
            'cses': cses,
            'y_in_cse': y_in_cse,
            'dydx_in_cse': dydx_in_cse,
        }

# y=x/(1+x) has the inverse x = y/(1-y), it is monotonic for x>-1 and x<-1 (inc/inc)
def main(yexprstr='x/(1+x)', lookup_N = 32, order=3, xlim=(0,1),
         x='x', save_temp=True, sample_N=2):
    tempd = './invnewton_build'
    yexpr = parse_expr(yexprstr, transformations=(
        standard_transformations + (implicit_multiplication_application,)))
    x = sympy.Symbol(x, real=True)
    yexpr = yexpr.subs({sympy.Symbol('x'): x})
    shutil.copy('invnewton_wrapper.pyx', tempd)
    pyxobj = pyx2obj('invnewton_wrapper.pyx', logger=logger)
    code = InvNewtonCode(yexpr, lookup_N, order, xlim, x,
                         save_temp=save_temp, logger=logger)
    ylim = code.ylim
    mod = code.compile_and_import_binary()
    os.unlink(pyxobj) # clean up
    mod.invnewton((ylim[0]+ylim[1])/2)

    yspan = ylim[1]-ylim[0]
    yarr = ylim[0]+np.random.random(sample_N)*yspan

    xarr = mod.invnewton(yarr)
    plt.plot(yarr, xarr)

    # we are plotting an inverse...
    plt.ylabel('x')
    plt.xlabel('y')
    plt.show()

argh.dispatch_command(main)
