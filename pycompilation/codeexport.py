from __future__ import print_function, division

# For performance reasons it is preferable that the
# numeric integration is performed in a compiled language
# the codeexport module provide classes enabling FirstOrderODESystem
# instances to be used as blueprint for generating, compiling
# and importing a binary which performs the computations.

# Both C, C++ and Fortran is considered, but since
# the codegeneration uses templates, one can easily extend
# the functionality to other languages.

# stdlib imports
import tempfile
import shutil
import re
import os

from collections import OrderedDict
from functools import reduce, partial
from operator import add


# External imports
import sympy


# Intrapackage imports
from helpers import import_, render_mako_template_to
from compilation import FortranCompilerRunner, CCompilerRunner


class Generic_Code(object):
    """

    Regarding syntax:
      C99 is assumed for 'C'
      Fortran 2008 (free form) is assumed for 'F'

    Attributes to optionally override:
    -`syntax`: any of the supported syntaxes ('C' or 'F')
    -`tempdir_basename`: basename of tempdirs created in e.g. /tmp/
    -`_cached_files`: Files that needs to be removed
        between compilations
    -`_basedir` the path to the directory which relative paths are given to
    """

    CompilerRunner = None # Set to a subclass of compilation.CompilerRunner
    syntax = None
    preferred_vendor = 'gnu'
    tempdir_basename = 'generic_code'
    _basedir = None
    _cached_files = None

    extension_name = 'generic_extension'

    def __init__(self, tempdir=None, save_temp=False, logger=None):
        """
        Arguments:
        - `tempdir`: Optional path to dir to write code files
        - `save_temp`: Save generated code files when garbage
            collected? (Default: False)

        """

        if self.syntax == 'C':
            self.wcode = sympy.ccode
        elif self.syntax == 'F':
            self.wcode = partial(sympy.fcode, source_format='free')

        self._basedir = self._basedir or os.path.dirname(__file__)

        if tempdir:
            self._tempdir = tempdir
            self._remove_tempdir_on_clean = False
        else:
            self._tempdir = tempfile.mkdtemp(self.tempdir_basename)
            self._remove_tempdir_on_clean = True
        self._save_temp = save_temp

        self.logger = logger

        if not os.path.isdir(self._tempdir):
            os.makedirs(self._tempdir)
            self._remove_tempdir_on_clean = True

        #
        for lstattr in ['_written_files', '_cached_files',
                        '_include_dirs', '_libraries',
                        '_library_dirs', '_include_dirs',
                        '_copy_files']:
            if not hasattr(self, lstattr):
                setattr(self, lstattr, [])
            else:
                setattr(self, lstattr,
                        getattr(self, lstattr) or [])

        # If .pyx files in _templates, add .c file to _cached_files
        self._cached_files += [x.replace('_template','').replace(
            '.pyx','.c') for x in self._templates if x.endswith('.pyx')]

        self._write_code()


    def variables(self):
        """
        Returns dictionary of variables for substituion
        suitable for use in the templates (formated according
        to the syntax of the language)
        """
        # To be overloaded
        return {}


    def _write_code(self):
        for path in self._cached_files:
            # Make sure we start with a clean slate
            rel_path = os.path.join(self._tempdir, path)
            if os.path.exists(rel_path):
                os.unlink(rel_path)
        for path in self._copy_files:
            # Copy files
            srcpath = os.path.join(self._basedir, path)
            dstpath = os.path.join(self._tempdir,
                         os.path.basename(path))
            shutil.copy(srcpath, dstpath)
            self._written_files.append(dstpath)

        subs = self.variables()
        for path in self._templates:
            # Render templates
            srcpath = os.path.join(self._basedir, path)
            outpath = os.path.join(self._tempdir,
                         os.path.basename(path).replace('_template', ''))
            render_mako_template_to(srcpath, outpath, subs)
            self._written_files.append(outpath)


    def compile_and_import_binary(self):
        self._compile()
        return import_(self.binary_path)


    @property
    def binary_path(self):
        return os.path.join(self._tempdir, self.extension_name)


    def clean(self):
        """ Delete temp dir if not save_temp set at __init__ """
        if not self._save_temp:
            map(os.unlink, self._written_files)
            if self._remove_tempdir_on_clean:
                shutil.rmtree(self._tempdir)


    def __del__(self):
        """
        When Generic_Code object is collected by GC
        self._tempdir is (possibly) deleted
        """
        self.clean()


    def _compile(self):
        self._compile_obj()
        self._compile_so()


    def _compile_obj(self, sources=None):
        sources = sources or self._source_files
        for f in sources:
            outpath = os.path.splitext(f)[0]+'.o'
            runner = self.CompilerRunner(
                f, outpath, run_linker=False,
                cwd=self._tempdir,
                inc_dirs=self._include_dirs,
                options=['pic', 'warn', 'fast'],
                preferred_vendor=self.preferred_vendor,
                logger=self.logger)
            runner.run()


    def _compile_so(self):
        # Generate shared object for importing:
        from distutils.sysconfig import get_config_vars
        pylibs = [x[2:] for x in get_config_vars(
            'BLDLIBRARY')[0].split() if x.startswith('-l')]
        cc = get_config_vars('BLDSHARED')[0]
        # We want something like: gcc, ['-pthread', ...
        compilername, flags = cc.split()[0], cc.split()[1:]
        runner = self.CompilerRunner(
            self._obj_files,
            self._so_file, flags,
            cwd=self._tempdir,
            inc_dirs=self._include_dirs,
            libs=self._libraries+pylibs,
            lib_dirs=self._library_dirs,
            preferred_vendor=self.preferred_vendor,
            logger=self.logger)
        runner.run()


class Cython_Code(Generic_Code):
    """
    Uses Cython's build_ext and distutils
    to simplify compilation
    """

    from Cython.Distutils import build_ext
    from distutils.core import setup
    from distutils.extension import Extension

    def _compile(self):
        sources = [os.path.join(
            self._tempdir, os.path.basename(x).replace(
                '_template', '')) for x \
            in self._source_files]
        setup(
            script_name =  'DUMMY_SCRIPT_NAME',
            script_args =  ['build_ext',  '--build-lib', self._tempdir],
            include_dirs = self._include_dirs,
            cmdclass = {'build_ext': build_ext},
            ext_modules = [
                Extension(
                    self.extension_name,
                    sources,
                    libraries=self._libraries,
                    library_dirs=self._library_dirs,
                    include_dirs=self._include_dirs),
                ]
            )


class C_Code(Generic_Code):
    """
    C code class
    """

    syntax = 'C'
    CompilerRunner = CCompilerRunner


class F90_Code(Generic_Code):
    """
    Fortran 90 code class
    """

    syntax = 'F'
    CompilerRunner = FortranCompilerRunner

    def __init__(self, *args, **kwargs):
        self._cached_files = self._cached_files or []
        # self._cached_files += [x+'.mod' for x in self._get_module_files(self._source_files)]
        self._cached_files += [x+'.mod' for x in self._get_module_files(self._templates)]
        super(F90_Code, self).__init__(*args, **kwargs)

    def _get_module_files(self, files):
        names = []
        for f in files:
            with open(os.path.join(self._basedir, f),'rt') as fh:
                for line in fh:
                    stripped_lower = line.strip().lower()
                    if stripped_lower.startswith('module'):
                        names.append(stripped_lower.split('module')[1].strip())
        return names

    @property
    def binary_path(self):
        return os.path.join(self._tempdir, self._so_file)


class Cython_Code(Generic_Code):
    """
    Uses Cython's build_ext and distutils
    to simplify compilation
    """

    from Cython.Distutils import build_ext
    from distutils.core import setup
    from distutils.extension import Extension

    def _compile(self):
        sources = [os.path.join(
            self._tempdir, os.path.basename(x).replace(
                '_template', '')) for x \
            in self._source_files]
        setup(
            script_name =  'DUMMY_SCRIPT_NAME',
            script_args =  ['build_ext',  '--build-lib', self._tempdir],
            include_dirs = self._include_dirs,
            cmdclass = {'build_ext': build_ext},
            ext_modules = [
                Extension(
                    self.extension_name,
                    sources,
                    libraries=self._libraries,
                    library_dirs=self._library_dirs,
                    include_dirs=self._include_dirs),
                ]
            )
