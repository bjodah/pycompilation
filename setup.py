#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import os
import shutil
from setuptools import setup

pkg_name = 'pycompilation'

RELEASE_VERSION = os.environ.get('%s_RELEASE_VERSION' % pkg_name.upper(), '')

# http://conda.pydata.org/docs/build.html#environment-variables-set-during-the-build-process
if os.environ.get('CONDA_BUILD', '0') == '1':
    try:
        RELEASE_VERSION = 'v' + io.open(
            '__conda_version__.txt', 'rt', encoding='utf-8'
        ).readline().rstrip()
    except IOError:
        pass


def _path_under_setup(*args):
    return os.path.join(os.path.dirname(__file__), *args)

release_py_path = _path_under_setup(pkg_name, '_release.py')

if (len(RELEASE_VERSION) > 1 and RELEASE_VERSION[0] == 'v'):
    TAGGED_RELEASE = True
    __version__ = RELEASE_VERSION[1:]
else:
    TAGGED_RELEASE = False
    # read __version__ attribute from _release.py:
    exec(io.open(release_py_path, encoding='utf-8').read())

tests = [
    'pycompilation.tests',
]


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

setup_kwargs = dict(
    name=pkg_name,
    version=__version__,
    author='Björn Dahlgren',
    author_email='bjodah@DELETEMEgmail.com',
    description='Package for compilation (meta programming).',
    license="BSD",
    url='https://github.com/bjodah/'+pkg_name,
    packages=[pkg_name] + tests,
    classifiers=classifiers,
    extras_require={
        'all': ['cython', 'appdirs', 'argh', 'joblib', 'pytest', 'numpy',
                'Sphinx', 'sphinx_rtd_theme', 'numpydoc', 'pytest-cov', 'pytest-flakes', 'pytest-pep8']
    }
)

if __name__ == '__main__':
    try:
        if TAGGED_RELEASE:
            # Same commit should generate different sdist
            # depending on tagged version (set ${pkg_name}_RELEASE_VERSION)
            # this will ensure source distributions contain the correct version
            shutil.move(release_py_path, release_py_path+'__temp__')
            open(release_py_path, 'wt').write(
                "__version__ = '{}'\n".format(__version__))
        setup(**setup_kwargs)
    finally:
        if TAGGED_RELEASE:
            shutil.move(release_py_path+'__temp__', release_py_path)
