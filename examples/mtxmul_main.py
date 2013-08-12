#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

import numpy as np

from pycompilation import (
    compile_sources, pyx2obj, compile_py_so,
    FortranCompilerRunner, import_
)

def run_compilation(tempd, logger=None):
    compile_sources(['../mtxmul.f90'], FortranCompilerRunner,
                    cwd=tempd, options=['pic', 'warn', 'fast','f90'],
                    run_linker=False, logger=logger)
    pyx2obj('../mtxmul_wrapper.pyx', cwd=tempd, logger=logger)
    so_file = compile_py_so(['mtxmul.o', 'mtxmul_wrapper.o'],
                            FortranCompilerRunner,
                            cwd=tempd, logger=logger)
    return os.path.join(tempd, so_file)

def main(logger):
    """
    Example program showing how to wrap fortran code using Cython
    """
    so_file_path = run_compilation('./mtxmul_build', logger=logger)
    mod = import_(so_file_path)

    A = np.random.random((7,9))
    B = np.random.random((9,13))
    C = mod.mtxmul(A,B)
    assert C.shape == (7, 13)
    assert np.allclose(np.dot(A,B), C)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__file__)
    main(logger=logger)
