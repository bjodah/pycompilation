import os
import tempfile
import shutil
import logging
from itertools import product
import time

import numpy as np

from pycompilation import pyx2obj, compile_sources, compile_py_so, import_
from pycompilation.util import render_mako_template_to

def run_compilation(tempd, logger=None):
    # Let's compile elemwise.c and wrap it using cython
    # source in elemwise_wrapper.pyx

    pyx2obj('elemwise_wrapper.pyx', cwd=tempd, logger=logger)

    compile_sources(['elemwise.c'], cwd=tempd,
                    options=['pic', 'warn', 'fast', 'c99'],
                    run_linker=False, logger=logger)

    so_file = compile_py_so(['elemwise.o', 'elemwise_wrapper.o'],
                  cwd=tempd, logger=logger
              )
    return os.path.join(tempd, so_file)

def generate_code(tempd):
    ops = [('add', '+'), ('sub', '-'), ('mul', '*')]
    ctypes = ['double', 'float']
    nptypes = ['float64', 'float32']
    #nptypes = [x.type.__name__ for x in map(np.dtype, ctypes)]
    types = zip(ctypes, nptypes)
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


def main(logger=None):
    tempd = './elemwise_build'
    generate_code(tempd)
    sofilepath = run_compilation(tempd, logger=logger)
    mod = import_(sofilepath)

    N = 1e6

    a = np.random.random(N)
    b = np.random.random(N)
    c = np.array(np.random.random(N), dtype=np.float32)
    d = np.array(np.random.random(N), dtype=np.float32)

    t1 = time.time()
    x = mod.elemadd(a,b)
    y = mod.elemadd(c,d)
    t2 = time.time()
    xref = a+b
    yref = c+d
    t3 = time.time()
    assert np.allclose(x, xref)
    assert np.allclose(y, yref)

    print('elemwise runtime divided by numpy runtime: {}'.format(
        (t2-t1)/(t3-t2)))

    t1 = time.time()
    x = mod.elemmul(a,b)
    y = mod.elemmul(c,d)
    t2 = time.time()
    xref = a*b
    yref = c*d
    t3 = time.time()
    assert np.allclose(x, a*b)
    assert np.allclose(y, c*d)

    print('elemwise runtime divided by numpy runtime: {}'.format(
        (t2-t1)/(t3-t2)))

    shutil.rmtree(tempd)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__file__)
    main(logger=logger)
