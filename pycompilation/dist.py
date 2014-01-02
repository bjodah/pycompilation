# -*- coding: utf-8 -*-

"""
Interaction with distutils
"""

import os
import re

from distutils.command import build_ext
from distutils.extension import Extension

from .compilation import extension_mapping, FortranCompilerRunner, CppCompilerRunner, compile_sources, link_py_so
from .util import copy, get_abspath, render_mako_template_to, import_

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
    """
    Arguments:
    -`template_regexps`: [(pattern1, target1, subsd1), ...] to generate templated code
    -`pass_extra_compile_args`: True/False, default: False, should ext.extra_compile_args be
        passed along?
    """
    instance = Extension(*args, **kwargs)
    instance.template_regexps = kwargs.pop('template_regexps', [])
    # use distutils extra_compile_args?
    instance._pass_extra_compile_args = kwargs.pop('pass_extra_compile_args', False)
    instance.pycompilation_compile_kwargs = kwargs.pop(
        'pycompilation_compile_kwargs', {})
    instance.pycompilation_link_kwargs = kwargs.pop(
        'pycompilation_link_kwargs', {})
    return instance


class clever_build_ext(build_ext.build_ext):
    """
    build_ext class for CleverExtension
    Support for template_regexps
    """
    def run(self):
        if self.dry_run: return # honor the --dry-run flag
        for ext in self.extensions:
            sources = []
            for f in ext.sources:
                # Either render a template or copy the source
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
                        break
                else:
                    copy(f,
                         os.path.join(self.build_temp,
                                      os.path.dirname(f)),
                         dest_is_dir=True,
                         create_dest_dirs=True)
                    sources.append(f)

            if ext._pass_extra_compile_args:
                # By default we do not pass extra_compile_kwargs
                # since it contains '-fno-strict-aliasing' which
                # harms performance.
                ext.pycompilation_compile_kwargs['flags'] =\
                    ext.extra_compile_args,
            # Compile sources to object files
            src_objs = compile_sources(
                sources,
                cwd=self.build_temp,
                inc_dirs=map(get_abspath, ext.include_dirs),
                lib_dirs=map(get_abspath, ext.library_dirs),
                defmacros=ext.define_macros,
                undefmacros=ext.undef_macros,
                libs=ext.libraries,
                **ext.pycompilation_compile_kwargs
            )

            # Link objects to a shared object
            abs_so_path = link_py_so(
                src_objs+ext.extra_objects,
                cwd=self.build_temp,
                flags=ext.extra_link_args,
                fort=any_fort(sources),
                cplus=any_cplus(sources),
                **ext.pycompilation_link_kwargs
            )
            copy(abs_so_path, self.get_ext_fullpath(
                ext.name))


def compile_link_import_py_ext(srcs, extname=None, build_dir=None,
                               compile_kwargs=None, link_kwargs=None):
    """
    Compiles sources in `srcs` to a shared object (python extension)
    which is imported. If shared object is newer than the sources, they
    are not recompiled but instead it is imported.

    Arguments:
    -`srcs`: [string], list of paths to sources
    -`extname`: string, name of extension default: None
        (taken from the last file in `srcs` - without extension)
    -`build_dir`: path to directory in which objects files etc. are generated
    -`compile_kwargs`: dict, keyword arguments passed to compile_sources
    -`link_kwargs`: dict, keyword arguments passed to link_py_so

    Returns:
    - the imported module

    Example:
    >>> mod = compile_link_import_py_ext(['fft.f90', 'convolution.cpp', 'fft_wrapper.pyx'])
    >>> Aprim = mod.fft(A)
    """
    build_dir = build_dir or '.'
    if extname == None:
        extname = os.path.splitext(os.path.basename(srcs[-1]))[0]

    try:
        mod = import_(os.path.join(build_dir, extname), srcs)
    except ImportError:
        objs = compile_sources(srcs, destdir=build_dir, **(compile_kwargs or {}))
        so = link_py_so(
            objs, cwd=build_dir, fort=any_fort(srcs), cplus=any_cplus(srcs),
            **(link_kwargs or {}))
        mod = import_(so)

    return mod
