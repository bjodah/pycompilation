import os
import tempfile
import shutil
import logging
from itertools import product
import time

import numpy as np

from pycompilation import pyx2obj, compile_sources, link_py_so, import_
from pycompilation.util import render_mako_template_to

from operator import add, mul, sub, div, pow

def run_compilation(tempd, logger=None):
    # Let's compile elemwise.c and wrap it using cython
    # source in elemwise_wrapper.pyx

    pyx2obj('elemwise_wrapper.pyx', cwd=tempd, logger=logger)

    compile_sources(['elemwise.c'], cwd=tempd,
                    options=['pic', 'warn', 'fast', 'openmp'],
                    std='c99',
                    run_linker=False, logger=logger)

    so_file = link_py_so(['elemwise.o', 'elemwise_wrapper.o'],
                  options=['openmp'], cwd=tempd, logger=logger
              )
    return os.path.join(tempd, so_file)


def mk_symbol_opformater(symb):
    def opformater(a,b):
        return symb.join((a,b))
    return opformater


def mk_call_opformater(token):
    def opformater(a,b):
        return token+'('+a+', '+b+')'
    return opformater

def mk_cond_call_opformater(token, mapping):
    def opformater(a,b,key):
        return token+mapping[key]+'('+a+', '+b+')'
    return opformater


def generate_code(tempd):
    ctypes = ['double', 'float']
    nptypes = ['float64', 'float32']
    vectypes = ['__m128d', '__m128']
    vecsizes = [2,4]
    #nptypes = [x.type.__name__ for x in map(np.dtype, ctypes)]
    mapping = {'double': 'd', 'float': 's'} # from SSE
    # only pairwise operators wrapped (same type) e.g. '_mm_add_pd'
    ops = [
        ('add', mk_symbol_opformater('+'), mk_cond_call_opformater('_mm_add_p', mapping)),
        ('sub', mk_symbol_opformater('-'), mk_cond_call_opformater('_mm_sub_p', mapping)),
        ('mul', mk_symbol_opformater('*'), mk_cond_call_opformater('_mm_mul_p', mapping)),
        ('div', mk_symbol_opformater('/'), mk_cond_call_opformater('_mm_div_p', mapping)),
        ('pow', mk_call_opformater('pow'), None),
    ]

    types = zip(ctypes, nptypes, vectypes, vecsizes)
    combos = list(product(ops, types))
    if not os.path.exists(tempd):
        os.mkdir(tempd)
    render_mako_template_to('elemwise_template.c',
                            os.path.join(tempd, 'elemwise.c'),
                            {'idxtype': 'int', 'combos': combos})

    render_mako_template_to('elemwise_wrapper_template.pyx',
                            os.path.join(tempd,'elemwise_wrapper.pyx'),
                            {'idxtype': 'int', 'ops': ops,
                             'types': types,
                             'combos': combos})


def bench_binary_op(py_op, cb, a, b):
    t1 = time.time()
    x = cb(a,b)
    t2 = time.time()
    xref = py_op(a,b)
    t3 = time.time()
    assert np.allclose(x, xref)
    return (t2-t1)/(t3-t2)



def main(logger=None, clean=False):
    tempd = tempfile.mkdtemp('elemwise')
    generate_code(tempd)
    sofilepath = run_compilation(tempd, logger=logger)
    mod = import_(sofilepath)

    N = 16*1024*1024 # 3*128 MB if RAM needed

    for py_op, dtype_ in product([add,mul,sub,pow],
                              [np.float64, np.float32]):
        a = np.array(np.random.random(N), dtype=dtype_)
        b = np.array(np.random.random(N), dtype=dtype_)
        cb = getattr(mod, 'elem'+py_op.__name__)
        print('{} ({}) runtime divided by numpy runtime: {}'.format(
            cb, dtype_, bench_binary_op(py_op, cb, a, b)))
        cb = getattr(mod, 'vec'+py_op.__name__, None)
        if cb != None:
            print('{} ({}) runtime divided by numpy runtime: {}'.format(
                cb, dtype_, bench_binary_op(py_op, cb, a, b)))


    if clean:
        shutil.rmtree(tempd)
    else:
        print("build files left in: {}".format(tempd))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__file__)
    main(logger=logger)
