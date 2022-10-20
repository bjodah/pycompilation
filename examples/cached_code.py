# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)

import os
import sys
from time import sleep
from textwrap import dedent

from appdirs import user_cache_dir
import numpy as np

from pycompilation import compile_link_import_strings

# Setup a cache dir with OS conventional path (use appdirs)
appauthor = "Some Name"
# TODO: .so file should carry version info in its name instead:
appname = os.path.splitext(os.path.basename(__file__))[0] + f"_{'_'.join(map(str, sys.version_info))}"
cachedir = user_cache_dir(appname, appauthor)
try:
    os.mkdir(cachedir)
except OSError:
    pass  # Folder already exists..

# Setup persistent cache (joblib):


def DiskCache(cachedir, methods):
    """
    Class factory for mixin class to help with caching.
    The _DiskCache mixin class uses joblib to pickle results.
    """
    class _DiskCache(object):

        cached_methods = methods

        def __init__(self, *args, **kwargs):
            from tempfile import mkdtemp
            from joblib import Memory
            self.cachedir = cachedir or mkdtemp()

            self.memory = Memory(location=self.cachedir)
            for method in self.cached_methods:
                setattr(self, method, self.memory.cache(getattr(self, method)))

            if not os.path.isdir(self.cachedir):
                raise OSError("Non-existent directory: ", self.cachedir)

            super(_DiskCache, self).__init__(*args, **kwargs)
    return _DiskCache


# Class representation of our model (a polynomial in this example)

class MyPoly(DiskCache(cachedir, methods=("diff", "as_fortran_module"))):
    """
    Polynomial object. Pickable. Persistent cache through DiskCache class.

    Examples
    --------
    >>> p = MyPoly((3,2,0,-5))  # 3 + 2*x - 5*x**3
    >>> p.as_fortran_module()  # doctest: +SKIP
    module MyPoly_mod
    use iso_c_binding, only: c_int, c_double
    implicit none
    private
    public MyPoly
    contains
    subroutine MyPoly(n, x, y) bind(c, name="MyPoly")
        integer(c_int), value, intent(in) :: n
        real(c_double), intent(in) :: x(n)
        real(c_double), intent(out) :: y(n)
        y = 3*x**0 + 2*x**1 + 0*x**2 + -5*x**3
    end subroutine
    end module MyPoly_mod

    """

    fort_mod_template = dedent('''
    module %(name)s_mod
    use iso_c_binding, only: c_int, c_double
    implicit none
    private
    public %(name)s

    contains

    subroutine %(name)s(n, x, y) bind(c, name="%(name)s")
        integer(c_int), value, intent(in) :: n
        real(c_double), intent(in) :: x(n)
        real(c_double), intent(out) :: y(n)
        y = %(expr)s
    end subroutine
    end module %(name)s_mod
    ''')

    cython_wrapper = dedent('''
    # -*- coding: utf-8 -*-
    cimport numpy as cnp
    import numpy as np

    cdef extern void %(name)s(int, double *, double *)

    def callback(double [::1] inp):
        cdef cnp.ndarray[cnp.float64_t, ndim=1] out = np.empty(
            inp.size, dtype=np.float64)
        %(name)s(inp.size, &inp[0], &out[0])
        return out
    ''')

    def __init__(self, coeffs):
        for coeff in coeffs:
            float(coeff)  # make sure coeffs are numbers.
        self.coeffs = tuple(coeffs)
        super(MyPoly, self).__init__()

    def __getstate__(self):
        return self.coeffs

    def __setstate__(self, state):
        self.coeffs = state
        super(MyPoly, self).__init__()

    def expr(self):
        return " + ".join([str(c)+"*x**"+str(p) for
                           p, c in enumerate(self.coeffs)])

    def as_fortran_module(self):
        print("Simulating long generation time (sleeping for 3 seconds.)")
        sleep(3)
        return self.fort_mod_template % {'expr': self.expr(),
                                         'name': self.__class__.__name__}

    def wrapper_code(self):
        return self.cython_wrapper % {'name': self.__class__.__name__}

    def diff(self, degree=1):
        if degree == 0:
            print("Simulating long manipulation time (sleeping for 3 s.)")
            sleep(3)
            return self
        else:
            return MyPoly(tuple(
                (p*c for p, c in enumerate(self.coeffs[1:], 1))
            )).diff(degree - 1)

    def __hash__(self):
        return hash(self.coeffs)

    def compile_link_import_py_ext(self):
        build_dir = os.path.join(self.memory.location, 'build')
        try:
            os.mkdir(build_dir)
        except OSError:
            pass  # Folder already exists..

        return compile_link_import_strings([
            (self.__class__.__name__+"_module.f90", self.as_fortran_module()),
            ("_"+self.__class__.__name__+".pyx", self.wrapper_code())
        ], build_dir=build_dir, include_dirs=[np.get_include()],
                                           only_update=True, logger=True)
