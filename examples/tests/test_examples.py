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

import pytest


tests = glob.glob(os.path.join(os.path.dirname(__file__), '../*_main.py'))


@pytest.mark.parametrize('pypath', tests)
def test_examples(pypath):
    p = subprocess.Popen(
        ['python', pypath, '--clean'],
        cwd=os.path.join(os.path.dirname(__file__), '..'))
    assert p.wait() == 0  # SUCCESS==0
