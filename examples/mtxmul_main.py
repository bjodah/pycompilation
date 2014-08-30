#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import shutil
import sys
import tempfile

import numpy as np

from pycompilation import compile_link_import_py_ext

source_files = ['mtxmul.f90', 'mtxmul_wrapper.pyx']

def main(logger=None, clean=False):
    """
    Example program showing how to wrap fortran code using Cython
    """
    build_dir = tempfile.mkdtemp('mtxmul')
    mod = compile_link_import_py_ext(
        source_files, build_dir=build_dir, logger=logger)

    A = np.random.random((7,9))
    B = np.random.random((9,13))
    C = mod.mtxmul(A,B)
    assert C.shape == (7, 13)
    assert np.allclose(np.dot(A,B), C)

    if clean:
        shutil.rmtree(build_dir)
    else:
        print("build files left in: {}".format(build_dir))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__file__)
    clean = False
    if len(sys.argv) > 1:
        clean = sys.argv[1] == 'clean'
    main(logger=logger, clean=clean)
