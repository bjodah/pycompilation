#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
import pycompilation

name_ = 'pycompilation'

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
)
