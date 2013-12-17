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
                options=ext.options,
                cwd=self.build_temp,
                inc_dirs=map(get_abspath, ext.include_dirs))
            abs_so_path = link_py_so(
                src_objs, cwd=self.build_temp,
                fort=any_fort(sources),
                cplus=any_cplus(sources))
            copy(abs_so_path, self.get_ext_fullpath(
                ext.name))
