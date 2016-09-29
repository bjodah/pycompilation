#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example program showing how to wrap fortran code using Cython
"""

from __future__ import print_function, division, absolute_import

import logging
import shutil
import tempfile

import argh
import numpy as np

from pycompilation import compile_link_import_py_ext

source_files = ['mtxmul.f90', 'mtxmul_wrapper.pyx']


def main(logger=False, clean=False):
    if logger:
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__file__)

    build_dir = tempfile.mkdtemp('mtxmul')
    mod = compile_link_import_py_ext(
        source_files, build_dir=build_dir, logger=logger,
        include_dirs=[np.get_include()])

    A = np.random.random((7, 9))
    B = np.random.random((9, 13))
    C = mod.mtxmul(A, B)
    assert C.shape == (7, 13)
    assert np.allclose(np.dot(A, B), C)

    if clean:
        shutil.rmtree(build_dir)
    else:
        print("build files left in: {}".format(build_dir))


if __name__ == '__main__':
    argh.dispatch_command(main)
