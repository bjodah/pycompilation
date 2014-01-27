# -*- coding: utf-8 -*-

import glob
import os
import subprocess


def run_example(pypath):
    p = subprocess.Popen(
        ['python', pypath, 'clean'],
        cwd=os.path.join(os.path.dirname(__file__),'..'))
    assert p.wait() == 0 # systems which have `make` have SUCCESS==0


def test_elemwise():
    run_example(os.path.join(
        os.path.dirname(__file__), '..', 'elemwise_main.py'))


def test_euclid():
    run_example(os.path.join(
        os.path.dirname(__file__), '..', 'euclid_main.py'))


def test_mtxmul():
    run_example(os.path.join(
        os.path.dirname(__file__), '..', 'mtxmul_main.py'))
