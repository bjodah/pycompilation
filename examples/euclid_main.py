#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
from shutil import copy
from pycompilation import fort2obj, cpp2obj, pyx2obj, compile_py_so, CppCompilerRunner, import_

def run_compilation(logger, tempd):
    """
    Compiles and links Cython wrapped C++ function (which calls into an
    OpenMP enabled Fortran 2003 routine)
    """
    copy('euclid.hpp', tempd)
    objs = []
    objs.append(fort2obj(
        '../euclid_enorm.f90', options=['pic', 'fast', 'warn', 'f2008', 'openmp'],
        cwd=tempd, logger=logger))
    objs.append(cpp2obj('../euclid.cpp', cwd=tempd, logger=logger))
    objs.append(pyx2obj('../euclid_wrapper.pyx', cplus=True, cwd=tempd, logger=logger))

    so_file = compile_py_so(objs, CppCompilerRunner, lib_options=['fortran', 'openmp'],
                            cwd=tempd, logger=logger)

    return os.path.join(tempd, so_file)


def main(logger):
    so_file_path = run_compilation(logger, 'euclid_build')
    mod = import_(so_file_path)

    l = [[3,4],[4,3]]
    n = mod.norm(l)
    assert abs(n[0]-5.0) < 1e-15
    assert abs(n[1]-5.0) < 1e-15

    l = [[1,1,1,1],[2,2,2,2],[3,3,3,3]]
    n = mod.norm(l)
    assert abs(n[0]-2.0) < 1e-15
    assert abs(n[1]-4.0) < 1e-15
    assert abs(n[2]-6.0) < 1e-15

    l = [[1,1,1,1],[],[2,2]]
    try:
        mod.norm(l)
    except RuntimeError:
        pass
    else:
        raise


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__file__)
    main(logger=logger)
