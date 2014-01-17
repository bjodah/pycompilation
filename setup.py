#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
import pycompilation

name_ = 'pycompilation'

classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: BSD License",
    "Operating System :: POSIX",
    "Programming Language :: Python",
    "Programming Language :: C",
    "Programming Language :: Cython",
    "Programming Language :: Fortran",
    "Topic :: Software Development :: Code Generators",
    "Topic :: Software Development :: Compilers",
    "Topic :: Software Development :: Libraries :: Python Modules"
]

setup(
    name=name_,
    version=pycompilation.__version__,
    author='Björn Dahlgren',
    author_email='bjodah@DELETEMEgmail.com',
    description='Python package for codegeneration and compilation (meta programming).',
    license = "BSD",
    url='https://github.com/bjodah/'+name_,
    download_url='https://github.com/bjodah/'+name_+'/archive/v'+pycompilation.__version__+'.tar.gz',
    packages=[name_],
    classifiers = classifiers
)
