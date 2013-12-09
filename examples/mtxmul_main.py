#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import logging

import numpy as np

from pycompilation import (
    compile_sources, pyx2obj, link_py_so,
    FortranCompilerRunner, import_
)

from pycompilation.util import term_fmt, copy

examples_dir =  os.path.abspath(os.path.dirname(__file__))
files = ['mtxmul.f90', 'mtxmul_wrapper.pyx']
options=['pic', 'warn', 'fast']

def run_compilation(**kwargs):
    for f in files:
        copy(os.path.join(examples_dir, f), kwargs.get('cwd', None))
    objs = compile_sources(files, options=options, **kwargs)
    return link_py_so(objs, fort=True, **kwargs)

def main(logger=None, clean=False):
    """
    Example program showing how to wrap fortran code using Cython
    """
    build_dir = tempfile.mkdtemp('mtxmul')
    so_file_path = run_compilation(cwd=build_dir, logger=logger)
    mod = import_(so_file_path)

    A = np.random.random((7,9))
    B = np.random.random((9,13))
    C = mod.mtxmul(A,B)
    assert C.shape == (7, 13)
    assert np.allclose(np.dot(A,B), C)
    print(term_fmt("Passed!",('green', 'black')))

    if clean:
        shutil.rmtree(build_dir)
    else:
        print("build files left in: {}".format(build_dir))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__file__)
    main(logger=logger)
