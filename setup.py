#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
import os

pkg_name = 'pycompilation'
release_py_path = os.path.join(pkg_name, '_release.py')
exec(open(release_py_path).read())

classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: BSD License",
    "Operating System :: POSIX",
    "Programming Language :: Python",
    "Programming Language :: C",
    "Programming Language :: C++",
    "Programming Language :: Cython",
    "Programming Language :: Fortran",
    "Topic :: Software Development :: Code Generators",
    "Topic :: Software Development :: Compilers",
    "Topic :: Software Development :: Libraries :: Python Modules"
]

setup(
    name=pkg_name,
    version=__version__,
    author='Björn Dahlgren',
    author_email='bjodah@DELETEMEgmail.com',
    description='Package for compilation (meta programming).',
    license="BSD",
    url='https://github.com/bjodah/'+pkg_name,
    download_url='https://github.com/bjodah/'+pkg_name +
    '/archive/v'+__version__+'.tar.gz',
    packages=[pkg_name],
    classifiers=classifiers
)
