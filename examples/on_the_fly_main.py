#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Compare complexity to on_the_fly_low_level...
"""

from __future__ import print_function, division, absolute_import, unicode_literals

import sys
import time

import numpy as np

from pycompilation.dist import compile_link_import_strings


sources_ = [
    ('exp_binary_sum.c', r"""
#include <math.h>
void exp_binary_sum(int n, const double * const restrict in, double * const restrict out){
    // Make sure len(in) == 2*len(out)
    for (int i=0; i<n; ++i){
        out[i] = log(exp(in[2*i]) + exp(in[2*i+1]));
    }
}
"""),
    ('_exp_binary_sum.pyx', r"""
import numpy as np
cimport numpy as cnp
cdef extern void c_exp_binbary_sum "exp_binary_sum" (int, const double * const, double * const)

def exp_binary_sum(double [:] inp):
    assert inp.size % 2 == 0
    cdef cnp.ndarray[cnp.float64_t, ndim=1] out = np.empty(inp.size / 2, dtype=np.float64)
    c_exp_binbary_sum(inp.size / 2, &inp[0], &out[0])
    return out
""")
]


def npy(data):
    return np.log(np.exp(data[::2]) + np.exp(data[1::2]))


def timeit(cb, data):
    t = time.time()
    for i in range(10):
        res = cb(data)
    return time.time()-t, res


def main():
    mod = compile_link_import_strings(
        sources_, options=['fast', 'warn', 'pic'], std='c99', logger=True)
    data = np.random.random(1000000)
    t_mod, res_mod = timeit(mod.exp_binary_sum, data)
    t_npy, res_npy = timeit(npy, data)
    assert np.allclose(res_mod, res_npy)
    print(t_mod, t_npy)


if __name__ == '__main__':
    main()
