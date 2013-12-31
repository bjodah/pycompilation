#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import logging

import numpy as np

from pycompilation.dist import compile_link_import_py_ext
from pycompilation.util import term_fmt

source_files = ['mtxmul.f90', 'mtxmul_wrapper.pyx']

def main(logger=None, clean=False):
    """
    Example program showing how to wrap fortran code using Cython
    """
    build_dir = tempfile.mkdtemp('mtxmul')
    mod = compile_link_import_py_ext(source_files, build_dir=build_dir)

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
