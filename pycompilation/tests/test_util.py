# -*- coding: utf-8 -*-

from __future__ import print_function, division, absolute_import

from pycompilation.util import uniquify


def test_uniquify():
    assert uniquify([1, 1, 2, 2]) == [1, 2]
