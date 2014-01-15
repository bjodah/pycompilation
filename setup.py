#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

name_ = 'pycompilation'
version_ = '0.2.6'

setup(
    name=name_,
    version=version_,
    author='Björn Dahlgren',
    author_email='bjodah@DELETEMEgmail.com',
    description='Python package for codegeneration and compilation (meta programming).',
    license = "BSD",
    url='https://github.com/bjodah/'+name_,
    download_url='https://github.com/bjodah/'+name_+'/archive/v'+version_+'.tar.gz',
    packages=[name_],
)
