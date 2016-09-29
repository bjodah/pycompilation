# -*- coding: utf-8 -*-

"""
Interaction with distutils
"""

from __future__ import print_function, division, absolute_import

import os
import re

from distutils.command import build_ext, sdist
from distutils.extension import Extension

from .compilation import (
    compile_sources, link_py_so, any_fort,
    any_cplus, simple_cythonize
)
from .util import (
    copy, get_abspath, missing_or_other_newer,
    MetaReaderWriter, FileNotFoundError, pyx_is_cplus, make_dirs
)


def PCExtension(*args, **kwargs):
    """
    Parameters
    ==========
    template_regexps: list of 3-tuples
        e.g. [(pattern1, target1, subsd1), ...], used to generate
        templated code
    pass_extra_compile_args: bool
        should ext.extra_compile_args be passed along? default: False
    """
    vals = {}

    intercept = {
        'build_callbacks': (),  # tuple of (callback, args, kwargs)
        'link_ext': True,
        'build_files': (),
        'dist_files': (),  # work around stackoverflow.com/questions/2994396/
        'template_regexps': [],
        'pass_extra_compile_args': False,  # use distutils extra_compile_args?
        'pycompilation_compile_kwargs': {},
        'pycompilation_link_kwargs': {},
    }
    for k, v in intercept.items():
        vals[k] = kwargs.pop(k, v)

    intercept2 = {
        'logger': None,
        'only_update': True,
    }
    for k, v in intercept2.items():
        vck = kwargs.pop(k, v)
        vck = vals['pycompilation_compile_kwargs'].pop(k, vck)
        vck = vck or vals['pycompilation_link_kwargs'].pop(k, vck)
        vals[k] = vck

    instance = Extension(*args, **kwargs)

    if vals['logger'] is True:
        # interpret as we should instantiate a logger
        import logging
        logging.basicConfig(level=logging.DEBUG)
        vals['logger'] = logging.getLogger('PCExtension')

    for k, v in vals.items():
        setattr(instance, k, v)

    return instance


def _copy_or_render_source(ext, f, output_dir, render_callback,
                           skip_copy=False):
    """
    Tries to do regex match for each (pattern, target, subsd) tuple
    in ext.template_regexps for file f.
    """
    # Either render a template or copy the source
    dirname = os.path.dirname(f)
    filename = os.path.basename(f)
    for pattern, target, subsd in ext.template_regexps:
        if re.match(pattern, filename):
            tgt = os.path.join(dirname, re.sub(
                pattern, target, filename))
            rw = MetaReaderWriter('.metadata_subsd')
            try:
                prev_subsd = rw.get_from_metadata_file(output_dir, f)
            except (FileNotFoundError, KeyError):
                prev_subsd = None

            render_callback(
                get_abspath(f),
                os.path.join(output_dir, tgt),
                subsd,
                only_update=ext.only_update,
                prev_subsd=prev_subsd,
                create_dest_dirs=True,
                logger=ext.logger)
            rw.save_to_metadata_file(output_dir, f, subsd)
            return tgt
    else:
        if not skip_copy:
            copy(f,
                 os.path.join(output_dir,
                              os.path.dirname(f)),
                 only_update=ext.only_update,
                 dest_is_dir=True,
                 create_dest_dirs=True,
                 logger=ext.logger)
        return f


def render_python_template_to(src, dest, subsd, only_update=False,
                              prev_subsd=None, create_dest_dirs=True,
                              logger=None):
        """
        Overload this function if you want to use a template engine such as
        e.g. mako.
        """
        if only_update:
            if subsd == prev_subsd:
                if not missing_or_other_newer(dest, src):
                    if logger:
                        msg = ("Did not re-render {}. "
                               "(destination newer + same dict)")
                        logger.info(msg.format(src))
                    return

        with open(src, 'rt') as ifh:
            data = ifh.read()  # Don't go crazy on file size...

        if create_dest_dirs:
            dest_dir = os.path.dirname(dest)
            if not os.path.exists(dest_dir):
                make_dirs(dest_dir)

        with open(dest, 'wt') as ofh:
            ofh.write(data % subsd)


class pc_build_ext(build_ext.build_ext):
    """
    build_ext class for PCExtension
    Support for template_regexps
    """

    render_callback = staticmethod(render_python_template_to)

    def run(self):
        if self.dry_run:
            return  # honor the --dry-run flag
        for ext in self.extensions:
            sources = []
            if ext.logger:
                ext.logger.info("Copying/rendering sources...")
            for f in ext.sources:
                sources.append(_copy_or_render_source(
                    ext, f, self.build_temp, self.render_callback))

            if ext.logger:
                ext.logger.info("Copying build_files...")
            for f in ext.build_files:
                copy(f, os.path.join(self.build_temp,
                                     os.path.dirname(f)),
                     only_update=ext.only_update,
                     dest_is_dir=True,
                     create_dest_dirs=True,
                     logger=ext.logger)

            if ext.pass_extra_compile_args:
                # By default we do not pass extra_compile_kwargs
                # since it contains '-fno-strict-aliasing' which
                # harms performance.
                ext.pycompilation_compile_kwargs['flags'] =\
                    ext.extra_compile_args,
            if ext.define_macros:
                ext.pycompilation_compile_kwargs['define'] =\
                    list(set(ext.define_macros +
                             ext.pycompilation_compile_kwargs['define']))
            if ext.undef_macros:
                ext.pycompilation_compile_kwargs['undef'] =\
                    list(set(ext.undef_macros +
                             ext.pycompilation_compile_kwargs['undef']))

            # Run build_callbaks if any were provided
            for cb, args, kwargs in ext.build_callbacks:
                cb(self.build_temp, self.get_ext_fullpath(
                    ext.name), ext, *args, **kwargs)

            # Compile sources to object files
            src_objs = compile_sources(
                sources,
                cwd=self.build_temp,
                include_dirs=list(map(get_abspath, ext.include_dirs)),
                logger=ext.logger,
                only_update=ext.only_update,
                **ext.pycompilation_compile_kwargs
            )

            if ext.logger:
                ext.logger.info(
                    "Copying files needed for distribution..")
            for f, rel_dst in ext.dist_files:
                rel_dst = rel_dst or os.path.basename(f)
                copy(
                    f,
                    os.path.join(
                        os.path.dirname(self.get_ext_fullpath(ext.name)),
                        rel_dst,
                    ),
                    only_update=ext.only_update,
                    logger=ext.logger,
                )

            # Link objects to a shared object
            if ext.link_ext:
                abs_so_path = link_py_so(
                    src_objs+ext.extra_objects,
                    cwd=self.build_temp,
                    flags=ext.extra_link_args,
                    library_dirs=list(map(get_abspath, ext.library_dirs)),
                    libraries=ext.libraries,
                    fort=any_fort(sources),
                    cplus=(((ext.language or '').lower() == 'c++') or
                           any_cplus(sources)),
                    logger=ext.logger,
                    only_update=ext.only_update,
                    **ext.pycompilation_link_kwargs
                )
                copy(
                    abs_so_path, self.get_ext_fullpath(ext.name),
                    only_update=ext.only_update,
                    create_dest_dirs=True, logger=ext.logger
                )


class pc_sdist(sdist.sdist):

    render_callback = staticmethod(render_python_template_to)

    def run(self):
        for ext in self.distribution.ext_modules:
            _sources = []
            for src in ext.sources:
                if src.endswith('.pyx'):
                    cy_kwargs = {
                        'cplus': pyx_is_cplus(src),
                        'include_path': ext.include_dirs
                    }
                    _sources.append(simple_cythonize(
                        src, os.path.dirname(src), **cy_kwargs))
                else:
                    # Copy or render
                    _sources.append(_copy_or_render_source(
                        ext, src, '.',
                        self.render_callback, skip_copy=True))
            ext.sources = _sources
        sdist.sdist.run(self)
