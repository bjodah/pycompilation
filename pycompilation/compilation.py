from __future__ import print_function, division

import os
import subprocess
import shutil

from .util import HasMetaData, missing_or_other_newer, get_abspath
from .helpers import (
    find_binary_of_command, uniquify, assure_dir,
    )


class CompilationError(Exception):
    pass


class CompilerRunner(HasMetaData):

    flag_dict = None # Lazy unified defaults for compilers
    metadata_filename = '.metadata_CompilerRunner'

    # subclass to be e.g. {'gcc': 'gnu', ...}
    compiler_name_vendor_mapping = None

    logger = None

    def __init__(self, sources, out, flags=None, run_linker=True,
                 compiler=None, cwd=None, inc_dirs=None, libs=None,
                 lib_dirs=None,
                 options=None, logger=None, preferred_vendor=None,
                 metadir=None):
        """
        Arguments:
        - `preferred_vendor`: key of compiler_dict
        """

        cwd = cwd or '.'

        if hasattr(sources, '__iter__'):
            self.sources = sources
        else:
            self.sources = [sources]

        self.out = out
        self.flags = flags or []
        self.metadir = metadir
        if compiler:
            self.compiler_name, self.compiler_binary = compiler
            if self.metadir:
                self.save_to_metadata_file(
                    self.metadir, 'vendor',
                    self.compiler_name_vendor_mapping[
                        self.compiler_name])
        else:
            # Find a compiler
            preferred_compiler_name = self.compiler_dict.get(
                preferred_vendor,None)
            self.compiler_name, self.compiler_binary = \
                self.find_compiler(preferred_compiler_name)
            if self.compiler_binary == None:
                raise RuntimeError(
                    "No compiler found (searched: {})".format(
                        ', '.join(self.compiler_dict.values())))
        self.cwd = cwd
        self.inc_dirs = inc_dirs or []
        self.libs = libs or []
        self.lib_dirs = lib_dirs or []
        self.options = options or []
        self.logger = logger
        if run_linker:
            # both gcc and ifort have '-c' flag for disabling linker
            self.flags = filter(lambda x: x != '-c', self.flags)
        else:
            self.flags.append('-c')

        for inc_dir in self.inc_dirs:
            self.flags.append('-I'+inc_dir)

        for lib_dir in self.lib_dirs:
            self.flags.append('-L'+lib_dir)

        for opt in self.options:
            extra_flags = self.flag_dict[self.compiler_name][opt]
            self.flags.extend(extra_flags)


    @classmethod
    def find_compiler(cls, preferred_compiler_name=None,
                      metadir=None):
        """
        Identify a suitable C/fortran/other compiler

        When it is possible that the user (un)installs a compiler
        inbetween compilations of object files we want to catch
        that. This method allows compiler choice to be stored in a
        pickled metadata file.  Provide metadir a dirpath to
        make the class save choice there in a file with
        cls.metadata_filename as name.
        """
        if metadir:
            try:
                pcn = cls.compiler_dict.get(cls.get_from_metadata_file(
                    metadir, 'vendor'),None)
                preferred_compiler_name = preferred_compiler_name or pcn
            except IOError:
                pass
        candidates = cls.flag_dict.keys()
        if preferred_compiler_name:
            if preferred_compiler_name in candidates:
                # Duplication doesn't matter
                candidates = [preferred_compiler_name] + candidates
        name, path = find_binary_of_command(candidates)
        if metadir:
            if cls.logger: logger.info(
                    'Wrote choice of compiler to: metadir')
            cls.save_to_metadata_file(metadir, 'compiler',
                                      (name, path))
            cls.save_to_metadata_file(
                metadir, 'vendor',
                cls.compiler_name_vendor_mapping[name])
        return name, path


    def run(self):
        self.flags = uniquify(self.flags)

        # Append output flag and name to tail of flags
        self.flags.extend(['-o', self.out])

        self.cmd = [self.compiler_binary] + self.flags + \
                   self.sources + ['-l'+x for x in self.libs]
        # Logging
        if self.logger: self.logger.info(
                'Executing: "{}"'.format(' '.join(self.cmd)))

        p = subprocess.Popen(self.cmd,
                             cwd=self.cwd,
                             #shell=True,
                             stdin= subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT
        )
        self.cmd_outerr = p.communicate()[0]
        self.cmd_returncode = p.returncode

        # Error handling
        if self.cmd_returncode != 0:
            raise CompilationError(
                ("Error executing '{}' in {}. "+\
                 "Commanded exited with status {}"+\
                 " after givning the following output: {}").format(
                     ' '.join(self.cmd), self.cwd, self.cmd_returncode,
                     str(self.cmd_outerr)))

        if self.logger and self.cmd_outerr: self.logger.info(
                '...with output:\n'+self.cmd_outerr)

        return self.cmd_outerr, self.cmd_returncode


class CCompilerRunner(CompilerRunner):

    compiler_dict = {
        'gnu': 'gcc',
        'intel': 'icc',
    }

    flag_dict = {
        'gcc': {
            'pic': ('-fPIC',),
            'warn': ('-Wall', '-Wextra'),
            'fast': ('-O3', '-march=native', '-ffast-math',
                     '-funroll-loops'),
            'c99': ('-std=c99',),
            'openmp': ('-fopenmp',),
        },
        'icc': {
            'pic': ('-fPIC',),
            'fast': ('-fast',),
            'openmp': ('-openmp',),
            'warn': ('-Wall',),
            'c99': ('-std=c99',),
        }
    }

    compiler_name_vendor_mapping = {'gcc': 'gnu', 'icc': 'intel'}


class FortranCompilerRunner(CompilerRunner):

    compiler_dict = {
        'gnu': 'gfortran',
        'intel': 'ifort',
    }

    flag_dict = {
        'gfortran': {
            'f90': ('-std=f2008',),
            'warn': ('-Wall', '-Wextra', '-Wimplicit-interface'),
        },
        'ifort': {
            'f90': ('-stand f08',),
            'warn': ('-warn', 'all',),
        }
    }

    compiler_name_vendor_mapping = {
        'gfortran': 'gnu',
        'ifort': 'intel'
    }


    def __init__(self, *args, **kwargs):
        # gfortran takes a superset of gcc arguments
        new_flag_dict = {
            'gfortran': CCompilerRunner.flag_dict['gcc'],
            'ifort': CCompilerRunner.flag_dict['icc'],
        }
        for key in ['gfortran', 'ifort']:
            new_flag_dict[key].update(self.flag_dict[key])
        self.flag_dict = new_flag_dict
        super(FortranCompilerRunner, self).__init__(*args, **kwargs)


def compile_sources(files, CompilerRunner_=CCompilerRunner,
                    destdir=None, cwd=None,
                    update_only=True, **kwargs):
    """
    Distutils does not allow to use .o files in compilation
    (see http://bugs.python.org/issue5372)
    hence the compilation of source files cannot be cached
    unless doing something like what compile_sources does.

    Arguments:
    -`files`: list of paths to source files, if cwd is given, the
        paths are taken as relative
    -`CompilerRunner_`: coulde be e.g.
        pycompilation.FortranCompilerRunner
    -`destdir`: path to output directory, if cwd is given, the path is
        taken as relative
    -`cwd`: current working directory. Specify to have compiler run in
        other directory.
    -`update_only`: True (default) implies only to compile sources
        newer than their object files.
    -`**kwargs`: keyword arguments pass along to CompilerRunner_
    """
    destdir = destdir or '.'
    destdir = get_abspath(destdir, cwd=cwd)
    dstpaths = []
    for f in files:
        name, ext = os.path.splitext(os.path.basename(f))
        fname = name+'.o' # .ext -> .o
        dst = os.path.join(destdir, fname)
        dstpaths.append(dst)
        if missing_or_other_newer(dst, f, cwd=cwd):
            runner = CompilerRunner_(
                [f], dst, cwd=cwd, **kwargs)
            runner.run()
        else:
            print("Found {}, did not recompile.".format(dst))
    return dstpaths


def compile_py_so(obj_files, CompilerRunner_=CCompilerRunner,
                  so_file=None, cwd=None, libs=None, **kwargs):
    """
    Generate shared object for importing

    Arguments:
    -`obj_files`: list of paths to object files to be linked
    -`CompilerRunner_`: An appropriate subclass of CompilerRunner
    -`so_file`: Name (path) of shared object file to create. If
         not specified it will have the basname of the last object
         file in `obj_files` but with the extensino '.so' (Unix
         conventin, Windows users may patch and make a pull request).
    """
    from distutils.sysconfig import get_config_vars
    pylibs = [x[2:] for x in get_config_vars(
        'BLDLIBRARY')[0].split() if x.startswith('-l')]
    cc = get_config_vars('BLDSHARED')[0]

    so_file = so_file or os.path.splitext(obj_files[-1])[0]+'.so'

    libs = libs or []

    # We want something like: gcc, ['-pthread', ...
    compilername, flags = cc.split()[0], cc.split()[1:]
    runner = CompilerRunner_(
        obj_files,
        so_file, flags,
        cwd=cwd,
        libs=libs+pylibs,
        **kwargs)
    runner.run()
    return so_file

def simple_cythonize(src, dstdir=None, cwd=None, logger=None,
                     full_module_name=None, only_update=False,
                     **kwargs):
    from Cython.Compiler.Main import (
        default_options, compile, CompilationOptions
    )

    assert src.lower().endswith('.pyx') or src.lower().endswith('.py')
    cwd = cwd or '.'
    dstdir = dstdir or '.'

    if cwd:
        ori_dir = os.getcwd()
    else:
        ori_dir = '.'
    os.chdir(cwd)

    # if not dstdir:
    #     dstdir = os.path.dirname(src)

    c_name = os.path.splitext(os.path.basename(src))[0] + '.c'

    dstfile = os.path.join(dstdir, c_name)

    if only_update:
        if not missing_or_other_newer(dstfile, src):
            logger.info('{} newer than {}, did not compile'.format(
                dstfile, src))
            return
    cy_options = CompilationOptions(default_options)
    cy_options.__dict__.update(kwargs)
    if logger: logger.info("Cythonizing {} to {}".format(src, dstfile))
    compile([src], cy_options, full_module_name=full_module_name)
    if os.path.abspath(os.path.dirname(src)) != os.path.abspath(dstdir):
        if os.path.exists(dstfile):
            os.unlink(dstfile)
        shutil.move(os.path.join(os.path.dirname(src), c_name),
                    dstdir)
    os.chdir(ori_dir)


def simple_py_c_compile_obj(src, dst=None, cwd=None, logger=None,
                            only_update=False, metadir=None, **kwargs):
    """
    Use e.g. on *.c file written from `simple_cythonize`
    """
    dst = dst or os.path.splitext(src)[0] + '.o'
    if only_update:
        if not missing_or_other_newer(dst, src):
            logger.info('{} newer than {}, did not compile'.format(
                dst, src))
            return dst

    from distutils.sysconfig import get_python_inc, get_config_vars
    inc_dirs = [get_python_inc()]
    inc_dirs.extend(kwargs.pop('inc_dirs',[]))

    flags = kwargs.pop('flags', [])

    compiler = kwargs.pop('compiler', None)

    cc = " ".join(get_config_vars(
        'CC', 'BASECFLAGS', 'OPT', 'CFLAGSFORSHARED'))

    if not compiler:
        compilern, du_flags = cc.split()[0], cc.split()[1:]
        flags += du_flags

    runner =CCompilerRunner([src], dst, flags, run_linker=False,
                            compiler=[compilern]*2, cwd=cwd,
                            inc_dirs=inc_dirs, metadir=metadir,
                            logger=logger, **kwargs)
    runner.run()
    return dst


def pyx2obj(pyxpath, objpath=None, interm_c_dir=None, cwd=None,
            logger=None, full_module_name=None, only_update=False,
            metadir=None, include_numpy=False, inc_dirs=None,
            cy_kwargs=None, gdb=False, **kwargs):
    """
    Conveninece function

    If cwd is specified, pyxpath and dst are taken to be relative
    If only_update is set to `True` the modification time is checked
    and compilation is only run if the source is newer than the
    destination
    """
    assert pyxpath.endswith('.pyx')

    cwd = cwd or '.'
    objpath = objpath or '.'

    if os.path.isdir(objpath):
        pyx_fname = os.path.basename(pyxpath)
        objpath = os.path.join(objpath, pyx_fname[:-4]+'.o')

    interm_c_dir = interm_c_dir or os.path.dirname(objpath)
    abs_interm_c_dir = get_abspath(interm_c_dir, cwd=cwd)
    assure_dir(abs_interm_c_dir)

    interm_c_file = os.path.join(
        abs_interm_c_dir, os.path.basename(pyxpath)[:-4] + '.c')

    cy_kwargs = cy_kwargs or {}
    if gdb:
        cy_kwargs['gdb_debug'] = True
        cy_kwargs['output_dir'] = cwd
    simple_cythonize(pyxpath, dstdir=interm_c_dir,
                     cwd=cwd, logger=logger,
                     full_module_name=full_module_name,
                     only_update=only_update, **cy_kwargs)

    inc_dirs = inc_dirs or []
    if include_numpy:
        import numpy
        numpy_inc_dir = numpy.get_include()
        if not numpy_inc_dir in inc_dirs:
            inc_dirs.append(numpy_inc_dir)

    return simple_py_c_compile_obj(
        interm_c_file, dst=objpath, cwd=cwd, logger=logger,
        only_update=only_update, metadir=metadir,
        inc_dirs=inc_dirs, **kwargs)
