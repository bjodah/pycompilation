# -*- coding: utf-8 -*-

"""
Tests all examples in Python subprocesses.
Note: if setting PYTHONPATH environment variable
for py.test: make sure paths are absolute.
"""

from __future__ import (
    print_function, division, absolute_import, unicode_literals
)


import glob
import os
import subprocess
import sys

import pytest


tests = glob.glob(os.path.join(os.path.dirname(__file__), '../*_main.py'))


@pytest.mark.parametrize('pypath', tests)
def test_examples(pypath):
    p = subprocess.Popen([sys.executable, pypath, '--clean'],
                         cwd=os.path.join(os.path.dirname(__file__), '..'))
    assert p.wait() == os.EX_OK


def test_cflags_ldflags_sundials():
    env = os.environ.copy()
    env["CFLAGS"] = os.environ.get("PYCOMPILATION_TESTING_SUNDIALS_CFLAGS", "")
    env["LDFLAGS"] = os.environ.get("PYCOMPILATION_TESTING_SUNDIALS_LDFLAGS", "")
    sundials_libs = os.environ.get("PYCOMPILATION_TESTING_SUNDIALS_LIBS",
                                   "sundials_nvecserial,sundials_cvode,sundials_sunlinsollapackdense,lapack,m")
    p = subprocess.Popen([sys.executable, "../external_lib_sundials.py", '--clean', '--libs', sundials_libs],
                         cwd=os.path.join(os.path.dirname(__file__)), env=env)
    assert p.wait() == os.EX_OK
