#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cython: language_level=3

import math
import os
import shutil
import tempfile
import uuid

import sympy as sym
import numpy as np
from scipy.special import binom

from pycompilation import compile_link_import_py_ext
_template_base = os.path.dirname(__file__) + "/external_lib_sundials_integrate_serial_template"
with open(_template_base + ".c89") as ifh:
    template_integrate_serial_c89 = ifh.read()
with open(_template_base + ".pyx") as ifh:
    template_integrate_serial_pyx = ifh.read()


class ODEsys:

    def __init__(self, rhs, ny, nparams):
        self.t = sym.Symbol("t", real=True)
        self.y = tuple(sym.Symbol("y%d" % i, real=True) for i in range(ny))
        self.p = tuple(sym.Symbol("p%d" % i, real=True) for i in range(nparams))
        self.f = tuple(rhs(self.t, self.y, self.p))
        assert len(self.f) == len(self.y), 'f is dy/dt'
        self.j = sym.Matrix(len(self.y), 1, self.f).jacobian(self.y)
        self.uid = uuid.uuid4().hex[:10]

    def generate_sources(self, build_dir):
        self.mod_name = 'ode_c_%s' % self.uid
        idxs = list(range(len(self.f)))
        subs = {}
        subs.update({s: sym.Symbol('y[%d]' % i) for i, s in enumerate(self.y)})
        subs.update({s: sym.Symbol('p[%d]' % i) for i, s in enumerate(self.p)})
        f_exprs = ['out[%d] = %s;' % (i, sym.ccode(self.f[i].xreplace(subs)))
                   for i in idxs]
        j_col_defs = ['realtype * const col_%d = SM_COLUMN_D(J, %d);' % (ci, ci)
                      for ci in idxs]
        j_exprs = ['col_%d[%d] = %s;' % (ci, ri, self.j[ri, ci].xreplace(subs))
                   for ci in idxs for ri in idxs if self.j[ri, ci] != 0]
        ctx = dict(
            func='\n    '.join(f_exprs + ['return 0;']),
            dense_jac='\n    '.join(j_col_defs + j_exprs + ['return 0;']),
        )
        sources = {
            build_dir + '/integrate_serial_%s.c' % self.uid: template_integrate_serial_c89 % ctx,
            build_dir + '/%s.pyx' % self.mod_name: template_integrate_serial_pyx % {'uid': self.uid}
        }
        for pth, content in sources.items():
            with open(pth, 'wt') as fh:
                fh.write(content)
        return list(sources.keys())


def analytic1(i, p, a):
    assert i > 0 and p >= 0 and a > 0
    return binom(p+i-1, p) * a**(i-1) * (a+1)**(-i-p)


def decay_dydt_factory(ny):
    # Generates a callback for evaluating a dydt-callback for
    # a chain of len(k) + 1 species with len(k) decays
    # with corresponding decay constants k

    def dydt(t, y, p):
        assert len(y) == ny and len(p) == ny-1
        exprs = []
        for idx in range(ny):
            expr = 0
            curr_key = idx
            prev_key = idx - 1
            if idx < ny-1:
                expr -= y[curr_key]*p[curr_key]
            if idx > 0:
                expr += y[prev_key]*p[prev_key]
            exprs.append(expr)
        return exprs
    return dydt


def get_special_chain(n, p, a):
    assert n > 1 and p >= 0 and a > 0
    y0 = np.zeros(n)
    y0[0] = 1
    k = [(i+p+1)*math.log(a+1) for i in range(n-1)]
    dydt = decay_dydt_factory(n)

    def check(vals, atol, rtol, forgiveness=1):
        # Check solution vs analytic reference:
        for i in range(n-1):
            val = vals[i]
            ref = analytic1(i+1, p, a)
            diff = val - ref
            acceptance = (atol + abs(ref)*rtol)*forgiveness
            assert abs(diff) < acceptance

    return y0, k, ODEsys(dydt, n, n-1), check


def main(verbose=False, clean=False, rtol=1e-8, atol=1e-8, savefig='',
         libs="sundials_nvecserial,sundials_cvode,sundials_sunlinsollapackdense,lapack,m"):
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__file__)
    else:
        logger = False

    build_dir = tempfile.mkdtemp('external_lib_sundials')

    npa = (7, 1, 5)
    y0, params, odesys, check = get_special_chain(*npa)
    source_files = odesys.generate_sources(build_dir)

    mod = compile_link_import_py_ext(
        source_files, build_dir=build_dir, logger=logger,
        include_dirs=[np.get_include()], options=("debug", "warn", "pic"),
        libraries=libs.split(','))
    tout = np.linspace(0, 1)
    yout, info = mod.solve_ivp(np.asarray(tout, dtype=np.float64),
                               np.asarray(y0, dtype=np.float64),
                               np.atleast_1d(np.asarray(params, dtype=np.float64)),
                               abstol=np.atleast_1d(np.asarray(atol, dtype=np.float64)),
                               reltol=rtol)
    assert info["status"] == 0 and info["num_steps"] > 5 and info["num_dls_jac_evals"] > 0
    forgive = 5  # relax analytic tolerances from those of solver
    check(yout[-1, :], atol, rtol, forgive)
    if savefig:
        from itertools import cycle
        import matplotlib.pyplot as plt
        plt.style.use('dark_background')
        fig, ax = plt.subplots(1, 1, figsize=(11, 5), dpi=300)
        dashes = cycle([[], [3, 1], [1, 1], [3, 1, 1, 1], [3, 1, 1, 1, 1, 1],
                        [3, 1, 3, 1, 1, 1], [3, 1, 1, 1, 1, 1, 1, 1]])
        for i, y in enumerate(yout.T):
            ax.plot(tout, y, label=str(i), dashes=next(dashes))
        ax.legend()
        fig.savefig(savefig)
    if clean:
        shutil.rmtree(build_dir)
    else:
        print("build files left in: {}".format(build_dir))


if __name__ == '__main__':
    import argh
    argh.dispatch_command(main)
