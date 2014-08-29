#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import sys
import tempfile

import shutil

from pycompilation import src2obj, link_py_so, import_module_from_file

examples_dir = os.path.abspath(os.path.dirname(__file__))
files = ['euclid.hpp', 'euclid_enorm.f90', 'euclid.cpp', 'euclid_wrapper.pyx']
options = ['pic', 'warn', 'fast']
options_omp = options+['openmp']


def run_compilation(**kwargs):
    """
    Compiles and links Cython wrapped C++ function
    (which calls into an OpenMP enabled Fortran 2003 routine)
    """
    for f in files:
        shutil.copy(f, kwargs['cwd'])
    objs = [
        src2obj('euclid_enorm.f90',
                options=options_omp,
                **kwargs),
        src2obj('euclid.cpp',
                std='c++0x',
                options=options,
                **kwargs),
        src2obj('euclid_wrapper.pyx',
                cplus=True, **kwargs)
    ]

    # Link a mixed C++/Fortran extension (shared object)
    return link_py_so(objs, cplus=True, fort=True,
                      options=options_omp, **kwargs)


def main(logger=None, clean=False):
    build_dir = tempfile.mkdtemp('euclid')
    so_file_path = run_compilation(logger=logger, cwd=build_dir)
    mod = import_module_from_file(so_file_path)

    l = [[3, 4], [4, 3]]
    n = mod.norm(l)
    assert abs(n[0]-5.0) < 1e-15
    assert abs(n[1]-5.0) < 1e-15

    l = [[1, 1, 1, 1], [2, 2, 2, 2], [3, 3, 3, 3]]
    n = mod.norm(l)
    assert abs(n[0]-2.0) < 1e-15
    assert abs(n[1]-4.0) < 1e-15
    assert abs(n[2]-6.0) < 1e-15

    l = [[1, 1, 1, 1], [], [2, 2]]
    try:
        mod.norm(l)
    except RuntimeError:
        pass
    else:
        raise

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
