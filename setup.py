#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from distutils.core import setup

pkg_name = 'pycompilation'
__version__ = '0.3.7'
IS_RELEASE=os.environ.get("IS_RELEASE", "0")
if IS_RELEASE != "1":
    __version__ += '.dev' # PEP386
if os.environ.get('CONDA_BUILD', None):
    with open('__conda_version__.txt', 'w') as f:
        if IS_RELEASE:
            f.write(__version__)
        else:
            f.write(__version__ + '.dev')

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
