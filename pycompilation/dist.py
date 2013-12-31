# -*- coding: utf-8 -*-

"""
Interaction with distutils
"""

import os
import re

from distutils.command import build_ext
from distutils.extension import Extension

from .compilation import extension_mapping, default_compile_options, FortranCompilerRunner, CppCompilerRunner, compile_sources, link_py_so
from .util import copy, get_abspath, render_mako_template_to

def is_fortran_file(src):
    name, ext = os.path.splitext(src)
    key = ext.lower()
    if key in extension_mapping:
        if extension_mapping[key][0] == FortranCompilerRunner:
            return True
    return False

def _any_X(srcs, cls):
    for src in srcs:
        if is_fortran_file(src): return True
    return False

def any_fort(srcs):
    return _any_X(srcs, FortranCompilerRunner)

def any_cplus(srcs):
    return _any_X(srcs, CppCompilerRunner)


# def _scan_for_tokens(src, tokens):
#     for line in open(src, 'rt'):
#         lower_line = line.lower()
#         if any([x in lower_line for x in tokens]):
#             return True
#     return False

# def uses_openmp(src):
#     if is_fortran_file(src):
#         tokens = ('$!omp ',)
#     else: # C / C++
#         tokens = ('#pragma omp ', '#include <omp.h>', '#include <omp>')
#     return _scan_for_tokens(src, tokens)

# def uses_lapack(src):
#     if is_fortran_file(src):
#         tokens = ()


def CleverExtension(*args, **kwargs):
    options = kwargs.pop('options', None)
    options_per_file = kwargs.pop('options_per_file', None)
    template_regexps = kwargs.pop('template_regexps', [])
    instance = Extension(*args, **kwargs)
    instance.options = options
    instance.template_regexps = template_regexps
    return instance


class clever_build_ext(build_ext.build_ext):
    def run(self):
        if self.dry_run: return # honor the --dry-run flag
        for ext in self.extensions:
            sources = []
            for f in ext.sources:
                dirname = os.path.dirname(f)
                filename = os.path.basename(f)
                for pattern, target, subsd in ext.template_regexps:
                    if re.match(pattern, filename):
                        tgt = os.path.join(dirname, re.sub(
                                pattern, target, filename))
                        render_mako_template_to(
                            get_abspath(f),
                            os.path.join(self.build_temp, tgt),
                            subsd,
                            only_update=True,
                            create_dest_dirs=True)
                        sources.append(tgt)
                        print(tgt)
                        break
                else:
                    copy(f,
                         os.path.join(self.build_temp,
                                      os.path.dirname(f)),
                         dest_is_dir=True,
                         create_dest_dirs=True)
                    sources.append(f)
            src_objs = compile_sources(
                sources,
                options=ext.options or default_compile_options,
                options_per_file=ext.options_per_file or None
                cwd=self.build_temp,
                inc_dirs=map(get_abspath, ext.include_dirs)
            )
            link_options = []
            abs_so_path = link_py_so(
                src_objs, cwd=self.build_temp,
                fort=any_fort(sources),
                cplus=any_cplus(sources),
                options=link_options,
            )
            copy(abs_so_path, self.get_ext_fullpath(
                ext.name))
