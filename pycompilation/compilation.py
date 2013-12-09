from __future__ import print_function, division

import os
import subprocess
import shutil
import re

from .util import HasMetaData, MetaReaderWriter, missing_or_other_newer, get_abspath, expand_collection_in_dict
from ._helpers import (
    find_binary_of_command, uniquify, assure_dir, CompilationError, FileNotFoundError
)

if os.name == 'posix': # Future improvement to make cross-platform
    flagprefix = '-'
    objext = '.o'
    sharedext = '.so'
elif os.name == 'nt':
    flagprefix = '/'
    objext = '.obj'
    sharedext = '.dll'
else:
    raise ImportError("Unknown os.name: {}".format(os.name))


default_compile_options = ('warn', 'pic', 'fast')


def get_mixed_fort_c_linker(vendor=None, metadir=None, cplus=False,
                            cwd=None):
    vendor = vendor or os.environ.get('COMPILER_VENDOR', None)


    if not vendor:
        metadir = get_abspath(metadir or '.', cwd=cwd)
        reader = MetaReaderWriter('.metadata_CompilerRunner')
        vendor = reader.get_from_metadata_file(metadir, 'vendor')

    if vendor == 'intel':
        if cplus:
            return (FortranCompilerRunner,
                    {'flags': ['-nofor_main', '-cxxlib']}, vendor)
        else:
            return (FortranCompilerRunner,
                    {'flags': ['-nofor_main']}, vendor)
    elif vendor == 'cray-gnu':
        if cplus:
            return (CppCompilerRunner,
                    {}, vendor)
        else:
            return (FortranCompilerRunner,
                    {}, vendor)
    elif vendor == 'gnu':
        if cplus:
            return (CppCompilerRunner,
                    {'lib_options': ['fortran']}, vendor)
        else:
            return (FortranCompilerRunner,
                    {}, vendor)


class CompilerRunner(object):

    compiler_dict = None # Subclass to vendor/binary dict

    standards = None # Subclass to a tuple of supported standards
                     # (first one will be the default)

    std_formater = None # Subclass to dict of binary/formater-callback

    option_flag_dict = None # Lazy unified defaults for compilers
    metadata_filename = '.metadata_CompilerRunner'

    # subclass to be e.g. {'gcc': 'gnu', ...}
    compiler_name_vendor_mapping = None

    logger = None

    # http://software.intel.com/en-us/articles/intel-mkl-link-line-advisor
    # MKL 11.1 x86-64, *nix, MKLROOT env. set, dynamic linking
    # This is _really_ ugly and not portable in any manner.
    vendor_options_dict = {
        'intel': {
            'lapack': {
                # 'linkline': [],
                # 'libs': ['mkl_avx', 'mkl_intel_lp64', 'mkl_core',
                #          'mkl_intel_thread', 'pthread', 'm'],
                # 'lib_dirs': ['${MKLROOT}/lib/intel64'],
                # 'inc_dirs': ['${MKLROOT}/include/intel64/lp64',
                #              '${MKLROOT}/include'],
                # 'flags': ['-openmp'],
                'linkline': ['-Wl,--start-group '+\
                             ' ${MKLROOT}/lib/intel64/libmkl_intel_ilp64.a'+\
                             ' ${MKLROOT}/lib/intel64/libmkl_core.a'+\
                             ' ${MKLROOT}/lib/intel64/libmkl_intel_thread.a'+\
                             ' -Wl,--end-group'],
                'libs': ['pthread', 'm'],
                'lib_dirs': ['${MKLROOT}/lib/intel64'],
                'inc_dirs': ['${MKLROOT}/include'],
                'flags': ['-openmp'],
                'def_macros': ['MKL_ILP64'],
                }
            },
        'gnu':{
            'lapack': {
                'libs': ['lapack', 'blas']
                }
            },
        'cray-gnu':{
            'lapack': {}
            },
        }


    def __init__(self, sources, out, flags=None, run_linker=True,
                 compiler=None, cwd=None, inc_dirs=None, libs=None,
                 lib_dirs=None, std=None, options=None, defmacros=None,
                 logger=None, preferred_vendor=None, metadir=None,
                 lib_options=None, only_update=False):
        """
        Arguments:
        - `preferred_vendor`: key of compiler_dict
        """

        cwd = cwd or '.'
        metadir = get_abspath(metadir or '.', cwd=cwd)

        if hasattr(sources, '__iter__'):
            self.sources = sources
        else:
            self.sources = [sources]

        self.out = out
        self.flags = flags or []
        self.metadir = metadir
        self.cwd = cwd
        if compiler:
            self.compiler_name, self.compiler_binary = compiler
            self.save_to_metadata_file(
                self.metadir, 'vendor',
                self.compiler_name_vendor_mapping[
                    self.compiler_name])
        else:
            # Find a compiler
            self.compiler_name, self.compiler_binary, \
                self.compiler_vendor = self.find_compiler(
                    preferred_vendor, metadir, self.cwd)
            if self.compiler_binary == None:
                raise RuntimeError(
                    "No compiler found (searched: {0})".format(
                        ', '.join(self.compiler_dict.values())))
        self.defmacros = defmacros or []
        self.inc_dirs = inc_dirs or []
        self.libs = libs or []
        self.lib_dirs = lib_dirs or []
        self.options = options or []
        self.std = std or self.standards[0]
        self.lib_options = lib_options or []
        self.logger = logger
        self.only_update = only_update
        if run_linker:
            # both gcc and ifort have '-c' flag for disabling linker
            self.flags = filter(lambda x: x != '-c', self.flags)
        else:
            self.flags.append('-c')

        if self.std:
            self.flags.append(self.std_formater[
                self.compiler_name](self.std))

        self.linkline = []

        for opt in self.options:
            self.flags.extend(self.option_flag_dict.get(
                self.compiler_name, {}).get(opt,[]))

            # extend based on vendor options dict
            def extend(l, k):
                l.extend(
                    self.vendor_options_dict.get(
                        self.compiler_vendor, {}).get(
                            opt, {}).get(k, []))
            extend(self.flags, 'flags')
            extend(self.defmacros, 'defmacors')
            extend(self.inc_dirs, 'inc_dirs')
            extend(self.lib_dirs, 'lib_dirs')
            extend(self.libs, 'libs')
            extend(self.linkline, 'linkline')

        # libs
        for lib_opt in self.lib_options:
            self.libs.extend(
                self.lib_dict[self.compiler_name][lib_opt])


    @classmethod
    def find_compiler(cls, preferred_vendor, metadir, cwd,
                      use_meta=True):
        """
        Identify a suitable C/fortran/other compiler

        When it is possible that the user (un)installs a compiler
        inbetween compilations of object files we want to catch
        that. This method allows compiler choice to be stored in a
        pickled metadata file.  Provide metadir a dirpath to
        make the class save choice there in a file with
        cls.metadata_filename as name.
        """
        cwd = cwd or '.'
        metadir = metadir or '.'
        metadir = os.path.join(cwd, metadir)
        used_metafile = False
        if not preferred_vendor and use_meta:
            try:
                preferred_vendor = cls.get_from_metadata_file(
                    metadir, 'vendor')
                #pcn = cls.compiler_dict.get(preferred_vendor, None)
                used_metafile = True
            except FileNotFoundError:
                pass
        candidates = cls.compiler_dict.keys()
        if preferred_vendor:
            if preferred_vendor in candidates:
                candidates = [preferred_vendor]+candidates
            else:
                raise ValueError("Unknown vendor {}".format(
                    preferred_vendor))
        name, path = find_binary_of_command([
            cls.compiler_dict[x] for x in candidates])
        if use_meta and not used_metafile:
            if not os.path.isdir(metadir):
                raise FileNotFoundError("Not a dir: {}".format(metadir))
            cls.save_to_metadata_file(metadir, 'compiler',
                                      (name, path))
            cls.save_to_metadata_file(
                metadir, 'vendor',
                cls.compiler_name_vendor_mapping[name])
            if cls.logger: logger.info(
                    'Wrote choice of compiler to: metadir')
        return name, path, cls.compiler_name_vendor_mapping[name]


    @property
    def cmd(self):
        """
        The command below covers most cases, if you need
        someting more complex subclass property(cmd)
        """
        cmd = [self.compiler_binary] +\
              self.flags + \
              ['-D'+x for x in self.defmacros] +\
              ['-I'+x for x in self.inc_dirs] +\
              self.sources + \
              ['-L'+x for x in self.lib_dirs] +\
              ['-l'+x for x in self.libs] +\
              self.linkline
        counted = []
        for envvar in re.findall('\$\{(\w+)\}', ' '.join(cmd)):
            if os.getenv(envvar) == None:
                if not envvar in counted:
                    counted.append(envvar)
                    msg = "Environment variable '{}' undefined.".format(
                        envvar)
                    raise CompilationError(msg)
                    self.logger.error(msg)
        return cmd


    def run(self):
        if self.only_update:
            for src in self.sources:
                if missing_or_other_newer(self.out, src, cwd=self.cwd):
                    break
            else:
                self.logger.info(('No source newer than {0}.'+\
                             ' Did not compile').format(
                                 self.out))
                return self.out

        self.flags = uniquify(self.flags)

        # Append output flag and name to tail of flags
        self.flags.extend(['-o', self.out])

        # Logging
        if self.logger: self.logger.info(
                'Executing: "{0}"'.format(' '.join(self.cmd)))

        env = os.environ.copy()
        env['PWD'] = self.cwd

        # NOTE: the ' '.join(self.cmd) part seems to be necessary for
        # intel compilers
        p = subprocess.Popen(' '.join(self.cmd),
                             shell=True,
                             cwd=self.cwd,
                             stdin= subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             env=env,
        )
        self.cmd_outerr = p.communicate()[0]
        self.cmd_returncode = p.returncode

        # Error handling
        if self.cmd_returncode != 0:
            raise CompilationError(
                ("Error executing '{0}' in {1}. "+\
                 "Command exited with status {2}"+\
                 " after givning the following output: {3}").format(
                     ' '.join(self.cmd), self.cwd, self.cmd_returncode,
                     str(self.cmd_outerr)))

        if self.logger and self.cmd_outerr: self.logger.info(
                '...with output:\n'+self.cmd_outerr)

        return self.cmd_outerr, self.cmd_returncode


class CCompilerRunner(CompilerRunner, HasMetaData):

    compiler_dict = {
        'gnu': 'gcc',
        'intel': 'icc',
        'cray-gnu': 'cc',
    }

    standards = ('c89', 'c90', 'c99', 'c11') # First is default

    std_formater = {
        'gcc': '-std={}'.format,
        'icc': '-std={}'.format,
        'cc': '-std={}'.format,
    }


    option_flag_dict = {
        'gcc': {
            'pic': ('-fPIC',),
            'warn': ('-Wall', '-Wextra'),
            'fast': ('-O3', '-march=native', '-ffast-math',
                     '-funroll-loops'),
            'openmp': ('-fopenmp',),
        },
        'icc': {
            'pic': ('-fPIC',),
            'fast': ('-fast',),
            'openmp': ('-openmp',),
            'warn': ('-Wall',),
        },
        'cc': { # assume PrgEnv-gnu (not portable, future improvement..)
            'pic': ('-fPIC',),
            'warn': ('-Wall', '-Wextra'),
            'fast': ('-O3', '-march=native', '-ffast-math',
                     '-funroll-loops'),
            'openmp': ('-fopenmp',),
        },
    }

    compiler_name_vendor_mapping = {'gcc': 'gnu', 'icc': 'intel', 'cc': 'cray-gnu'}


def _mk_flag_filter(cmplr_name): # helper for class initialization
    not_welcome = {'g++': ("Wimplicit-interface",)}#"Wstrict-prototypes",)}
    if cmplr_name in not_welcome:
        def fltr(x):
            for nw in not_welcome[cmplr_name]:
                if nw in x: return False
            return True
    else:
        def fltr(x):
            return True
    return fltr


class CppCompilerRunner(CompilerRunner, HasMetaData):

    compiler_dict = {
        'gnu': 'g++',
        'intel': 'icpc',
        'cray-gnu': 'CC',
    }

    standards = ('c++98', 'c++11') # First is the default

    std_formater = {
        'g++': '-std={}'.format,
        'icpc': '-std={}'.format,
        'cray-gnu': '-std={}'.format,
    }

    option_flag_dict = {
        'g++': {
        },
        'icpc': {
        },
        'CC': { # assume PrgEnv-gnu (not portable, future improvement..)
        }
    }

    lib_dict = {
        'g++': {
            'fortran': ('gfortranbegin', 'gfortran'),
            'openmp': ('gomp',),
        },
        'icpc': {
            'openmp': ('iomp5',),
        },
        'cray-gnu': {# assume PrgEnv-gnu (not portable, future improvement..)
            'fortran': ('gfortranbegin', 'gfortran'),
            'openmp': ('gomp',),
        },

    }

    compiler_name_vendor_mapping = {'g++': 'gnu', 'icpc': 'intel', 'CC': 'cray-gnu'}

    def __init__(self, *args, **kwargs):
        # g++ takes a superset of gcc arguments
        new_option_flag_dict = {
            'g++': CCompilerRunner.option_flag_dict['gcc'].copy(),
            'icpc': CCompilerRunner.option_flag_dict['icc'].copy(),
            'CC': CCompilerRunner.option_flag_dict['cc'].copy(),
        }
        for key in ['g++', 'icpc', 'CC']:
            if self.option_flag_dict[key]:
                fltr = _mk_flag_filter(key)
                keys, values = zip(*self.option_flag_dict[key].items())
                new_option_flag_dict[key].update(dict(zip(
                    keys, filter(fltr, values))))
        self.option_flag_dict = new_option_flag_dict
        super(CppCompilerRunner, self).__init__(*args, **kwargs)


class FortranCompilerRunner(CompilerRunner, HasMetaData):

    standards = (None, 'f95', 'f2003', 'f2008') #First is default (F77)

    std_formater = {
        'gfortran': '-std={}'.format,
        'ifort': lambda x: '-stand f{}'.format(x[-2:]), # f2008 => f08
        'ftn': '-std={}'.format,
    }

    compiler_dict = {
        'gnu': 'gfortran',
        'intel': 'ifort',
        'cray-gnu': 'ftn',
    }

    option_flag_dict = {
        'gfortran': {
            'warn': ('-Wall', '-Wextra', '-Wimplicit-interface'),
        },
        'ifort': {
            'warn': ('-warn', 'all',),
        },
        'ftn': { # assume PrgEnv-gnu (not portable, future improvement..)
            'f2008': ('-std=f2008',),
            'warn': ('-Wall', '-Wextra', '-Wimplicit-interface'),
        },
    }

    lib_dict = {
        'gfortran': {
            'openmp': ('gomp',),
        },
        'ifort': {
            'openmp': ('iomp5',),
        },
        'cray-gnu': {# assume PrgEnv-gnu (not portable, future improvement..)
            'openmp': ('gomp',),
        },

    }

    compiler_name_vendor_mapping = {
        'gfortran': 'gnu',
        'ifort': 'intel',
        'ftn': 'cray-gnu', # obvious deficiency with current method
    }


    def __init__(self, *args, **kwargs):
        # gfortran takes a superset of gcc arguments
        new_option_flag_dict = {
            'gfortran': CCompilerRunner.option_flag_dict['gcc'].copy(),
            'ifort': CCompilerRunner.option_flag_dict['icc'].copy(),
            'ftn': CCompilerRunner.option_flag_dict['cc'].copy(),
        }
        for key in ['gfortran', 'ifort', 'ftn']:
            new_option_flag_dict[key].update(self.option_flag_dict[key])
        self.option_flag_dict = new_option_flag_dict

        super(FortranCompilerRunner, self).__init__(*args, **kwargs)


def compile_sources(files, CompilerRunner_=None,
                    destdir=None, cwd=None, **kwargs):
    """
    Distutils does not allow to use object files in compilation
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
    -`only_update`: True (default) implies only to compile sources
        newer than their object files.
    -`**kwargs`: keyword arguments pass along to CompilerRunner_
    """
    destdir = destdir or '.'
    #destdir = get_abspath(destdir, cwd=cwd)
    dstpaths = []
    for f in files:
        name, ext = os.path.splitext(os.path.basename(f))
        dstpaths.append(src2obj(f, CompilerRunner_,
                                destdir, cwd=cwd, **kwargs))
    return dstpaths


def link_py_so(obj_files, CompilerRunner_=None,
               so_file=None, cwd=None, libs=None,
               cplus=False, fort=False, **kwargs):
    """
    Generate shared object for importing

    Arguments:
    -`obj_files`: list of paths to object files to be linked
    -`CompilerRunner_`: An appropriate subclass of CompilerRunner
    -`so_file`: Name (path) of shared object file to create. If
         not specified it will have the basname of the last object
         file in `obj_files` but with the extensino '.so' (Unix
         conventin, Windows users may patch and make a pull request).

    return the absolute to the generate shared object
    """
    libs = libs or []
    so_file = so_file or os.path.splitext(obj_files[-1])[0]+sharedext

    if not CompilerRunner_:
        if fort:
            CompilerRunner_, extra_kwargs, vendor = \
                get_mixed_fort_c_linker(
                    vendor=kwargs.get('vendor', None),
                    metadir=kwargs.get('metadir', None),
                    cplus=cplus,
                    cwd=cwd,
                )
            for k,v in extra_kwargs.items():
                expand_collection_in_dict(kwargs, k, v)
        else:
            if cplus:
                CompilerRunner_ = CppCompilerRunner
            else:
                CompilerRunner_ = CCompilerRunner

    from distutils.sysconfig import get_config_vars
    inc_dirs = kwargs.pop('inc_dirs', [])
    lib_dirs = kwargs.pop('lib_dirs', [])
    libs += [x[2:] for x in get_config_vars(
        'BLDLIBRARY')[0].split() if x.startswith('-l')]
    cc = get_config_vars('BLDSHARED')[0]

    # We want something like: gcc, ['-pthread', ...
    compilername, flags = cc.split()[0], cc.split()[1:]

    # Grab inc_dirs
    inc_dirs += filter(lambda x: x.startswith('-I'), flags)
    flags = filter(lambda x: not x.startswith('-I'), flags)

    # Grab lib_dirs
    lib_dirs += [x[2:] for x in filter(
        lambda x: x.startswith('-L'), flags)]
    flags = filter(lambda x: not x.startswith('-L'), flags)

    flags.extend(kwargs.pop('flags',[]))

    so_file = get_abspath(so_file, cwd=cwd)
    runner = CompilerRunner_(
        obj_files, so_file, flags,
        cwd=cwd,
        inc_dirs=inc_dirs,
        libs=libs,
        lib_dirs=lib_dirs,
        **kwargs)
    runner.run()
    return so_file


def simple_cythonize(src, dstdir=None, cwd=None, logger=None,
                     full_module_name=None, only_update=False,
                     **cy_kwargs):
    """
    Generates a .cpp file is cplus=True, else a .c file.
    """
    from Cython.Compiler.Main import (
        default_options, CompilationOptions
    )
    from Cython.Compiler.Main import compile as cy_compile

    assert src.lower().endswith('.pyx') or src.lower().endswith('.py')
    cwd = cwd or '.'
    dstdir = dstdir or '.'

    ext = '.cpp' if cy_kwargs['cplus'] else '.c'
    c_name = os.path.splitext(os.path.basename(src))[0] + ext

    dstfile = os.path.join(dstdir, c_name)

    if only_update:
        if not missing_or_other_newer(dstfile, src, cwd=cwd):
            logger.info(
                '{0} newer than {1}, did not re-cythonize.'.format(
                dstfile, src))
            return dstfile

    if cwd:
        ori_dir = os.getcwd()
    else:
        ori_dir = '.'
    os.chdir(cwd)

    cy_options = CompilationOptions(default_options)
    cy_options.__dict__.update(cy_kwargs)
    if logger: logger.info("Cythonizing {0} to {1}".format(
            src, dstfile))
    cy_compile([src], cy_options, full_module_name=full_module_name)
    if os.path.abspath(os.path.dirname(
            src)) != os.path.abspath(dstdir):
        if os.path.exists(dstfile):
            os.unlink(dstfile)
        shutil.move(os.path.join(os.path.dirname(src), c_name),
                    dstdir)
    os.chdir(ori_dir)
    return dstfile


extension_mapping = {
    '.c': (CCompilerRunner, None),
    '.cpp': (CppCompilerRunner, None),
    '.cxx': (CppCompilerRunner, None),
    '.f'  : (FortranCompilerRunner, None),
    '.for': (FortranCompilerRunner, None),
    '.ftn': (FortranCompilerRunner, None),
    '.f90': (FortranCompilerRunner, 'f08'), # ifort only knows about .f90
    '.f95': (FortranCompilerRunner, 'f95'),
    '.f03': (FortranCompilerRunner, 'f2003'),
    '.f08': (FortranCompilerRunner, 'f2008'),
}


def src2obj(srcpath, CompilerRunner_=None, objpath=None,
            only_update=False, cwd=None, out_ext=None, inc_py=False,
            **kwargs):
    name, ext = os.path.splitext(os.path.basename(srcpath))
    objpath = objpath or '.'
    out_ext = out_ext or objext
    if os.path.isdir(objpath):
        objpath = os.path.join(objpath, name+out_ext)

    inc_dirs = kwargs.pop('inc_dirs',[])
    if inc_py:
        from distutils.sysconfig import get_python_inc, get_config_vars
        inc_dirs += [get_python_inc()]


    if CompilerRunner_ == None:
        if ext.lower() == '.pyx':
            return pyx2obj(srcpath, objpath=objpath,
                           inc_dirs=inc_dirs,
                           cwd=cwd, **kwargs)
        CompilerRunner_, std = extension_mapping[ext.lower()]
        if not 'std' in kwargs: kwargs['std'] = std

    # src2obj implies not running the linker...
    run_linker = kwargs.pop('run_linker', False)

    if only_update:
        if not missing_or_other_newer(objpath, srcpath, cwd=cwd):
            msg = "Found {0}, did not recompile.".format(objpath)
            if 'logger' in kwargs:
                kwargs['logger'].info(msg)
            else:
                print(msg)
            return objpath
    if os.path.exists(objpath):
        # make sure failed compilation kills the party..
        os.unlink(objpath)
    runner = CompilerRunner_(
        [srcpath], objpath, inc_dirs=inc_dirs,
        run_linker=run_linker, cwd=cwd, **kwargs)
    runner.run()
    return objpath


def pyx2obj(pyxpath, objpath=None, interm_c_dir=None, cwd=None,
            logger=None, full_module_name=None, only_update=False,
            metadir=None, include_numpy=False, inc_dirs=None,
            cy_kwargs=None, gdb=False, cplus=False, **kwargs):
    """
    Convenience function

    If cwd is specified, pyxpath and dst are taken to be relative
    If only_update is set to `True` the modification time is checked
    and compilation is only run if the source is newer than the
    destination

    include_numpy: convenice flag for cython code cimporting numpy
    """
    assert pyxpath.endswith('.pyx')
    cwd = cwd or '.'
    objpath = objpath or '.'
    interm_c_dir = interm_c_dir or os.path.dirname(objpath)

    abs_objpath = get_abspath(objpath, cwd=cwd)

    if os.path.isdir(abs_objpath):
        pyx_fname = os.path.basename(pyxpath)
        name, ext = os.path.splitext(pyx_fname)
        objpath = os.path.join(objpath, name+objext)

    cy_kwargs = cy_kwargs or {}
    cy_kwargs['output_dir'] = cwd
    cy_kwargs['cplus'] = cplus
    if gdb:
        cy_kwargs['gdb_debug'] = True
    if inc_dirs:
        cy_kwargs['include_path'] = inc_dirs

    interm_c_file = simple_cythonize(
        pyxpath, dstdir=interm_c_dir,
        cwd=cwd, logger=logger,
        full_module_name=full_module_name,
        only_update=only_update, **cy_kwargs)

    inc_dirs = inc_dirs or []
    if include_numpy:
        import numpy
        numpy_inc_dir = numpy.get_include()
        if not numpy_inc_dir in inc_dirs:
            inc_dirs.append(numpy_inc_dir)

    flags = kwargs.pop('flags', [])
    flags.extend(['-fno-strict-aliasing'])
    options = kwargs.pop('options', [])
    if not 'pic' in options: options.append('pic')
    if not 'warn' in options: options.append('warn')
    if cplus:
        std = kwargs.pop('std', 'c++11')
    else:
        std = kwargs.pop('std', 'c99')
    return src2obj(
        interm_c_file,
        objpath=objpath,
        cwd=cwd,
        only_update=only_update,
        metadir=metadir,
        inc_dirs=inc_dirs,
        flags=flags,
        std=std,
        options=options,
        logger=logger,
        inc_py = True,
        **kwargs)
