# -*- coding: utf-8 -*-

"""
Interaction with distutils
"""

import os

from distutils.command import build_ext
from distutils.extension import Extension

from .compilation import extension_mapping, default_compile_options, FortranCompilerRunner, CppCompilerRunner, compile_sources, link_py_so
from .util import copy, get_abspath

def _any_X(srcs, cls):
    for src in srcs:
        name, ext = os.path.splitext(src)
        key = ext.lower()
        if key in extension_mapping:
            if extension_mapping[key][0] == FortranCompilerRunner:
                return True
    return False

def any_fort(srcs):
    return _any_X(srcs, FortranCompilerRunner)

def any_cplus(srcs):
    return _any_X(srcs, CppCompilerRunner)

def CleverExtension(*args, **kwargs):
    options = kwargs.pop('options', default_compile_options)
    instance = Extension(*args, **kwargs)
    instance.options = options
    return instance


class clever_build_ext(build_ext.build_ext):
    def run(self):
        if self.dry_run: return # honor the --dry-run flag
        for ext in self.extensions:
            for f in ext.sources:
                copy(f, self.build_temp, dest_is_dir=True,
                     create_dest_dirs=True)
            src_objs = compile_sources(
                map(os.path.basename, ext.sources),
                options=ext.options,
                cwd=self.build_temp,
                inc_dirs=map(get_abspath, ext.include_dirs))
            abs_so_path = link_py_so(
                src_objs, cwd=self.build_temp,
                fort=any_fort(ext.sources),
                cplus=any_cplus(ext.sources))
            copy(abs_so_path, self.get_ext_fullpath(
                'finitediff._finitediff'))
