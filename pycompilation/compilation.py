from __future__ import print_function, division

import os
import subprocess
import shutil

from .util import HasMetaData, missing_or_other_newer, get_abspath
from .helpers import (
    find_binary_of_command, uniquify, assure_dir, expand_collection_in_dict
    )


class CompilationError(Exception):
    pass


def get_mixed_fort_c_linker(vendor=None, metadir=None, cplus=False):
    class Reader(HasMetaData):
        metadata_filename = '.metadata_CompilerRunner'

    vendor = vendor or os.environ.get('COMPILER_VENDOR', None)

    reader = Reader()

    if not vendor:
        try:
            metadir = metadir or '.'
            vendor = reader.get_from_metadata_file(metadir, 'vendor')
        except IOError:
            vendor = 'gnu'

    if vendor == 'intel':
        if cplus:
            return (FortranCompilerRunner,
                    {'flags': ['-nofor_main', '-cxxlib']}, vendor)
        else:
            return (FortranCompilerRunner,
                    {'flags': ['-nofor_main']}, vendor)
    elif vendor == 'gnu':
        if cplus:
            return (CppCompilerRunner,
                    {'lib_options': ['fortran']}, vendor)
        else:
            return (FortranCompilerRunner,
                    {}, vendor)
            #(CCompilerRunner, {'lib_options': ['fortran']}, vendor)



class CompilerRunner(object):

    flag_dict = None # Lazy unified defaults for compilers
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
                'flags': ['-DMKL_ILP64', '-openmp'],
            }
        },
        'gnu':{
            'lapack': {
                'libs': ['lapack', 'blas']
            }
        }
    }


    def __init__(self, sources, out, flags=None, run_linker=True,
                 compiler=None, cwd=None, inc_dirs=None, libs=None,
                 lib_dirs=None, options=None, logger=None,
                 preferred_vendor=None, metadir=None, lib_options=None,
                 only_update=False):
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
            self.compiler_name, self.compiler_binary, \
                self.compiler_vendor = self.find_compiler(
                    preferred_vendor)
            if self.compiler_binary == None:
                raise RuntimeError(
                    "No compiler found (searched: {})".format(
                        ', '.join(self.compiler_dict.values())))
        self.cwd = cwd
        self.inc_dirs = inc_dirs or []
        self.libs = libs or []
        self.lib_dirs = lib_dirs or []
        self.options = options or []
        self.lib_options = lib_options or []
        self.logger = logger
        self.only_update = only_update
        if run_linker:
            # both gcc and ifort have '-c' flag for disabling linker
            self.flags = filter(lambda x: x != '-c', self.flags)
        else:
            self.flags.append('-c')

        for opt in self.options:
            self.flags.extend(self.flag_dict.get(
                self.compiler_name, {}).get(opt,[]))

            # extend based on vendor options dict
            def extend(l, k):
                l.extend(self.vendor_options_dict.get(
                self.compiler_vendor,{}).get(
                    opt, {}).get(
                        k, []))
            extend(self.flags, 'flags')
            extend(self.inc_dirs, 'inc_dirs')
            extend(self.lib_dirs, 'lib_dirs')
            extend(self.libs, 'libs')
            extend(self.sources, 'linkline')

        # libs
        for lib_opt in self.lib_options:
            self.libs.extend(
                self.lib_dict[self.compiler_name][lib_opt])



    @classmethod
    def find_compiler(cls, preferred_vendor=None,
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
        if not preferred_vendor:
            if metadir:
                try:
                    pcn = cls.compiler_dict.get(
                        cls.get_from_metadata_file(
                            metadir, 'vendor'),None)
                    preferred_vendor = preferred_vendor or pcn
                    used_metafile = True
                except IOError:
                    used_metafile = False
        candidates = cls.compiler_dict.keys()
        if preferred_vendor:
            if preferred_vendor in candidates:
                candidates = [preferred_vendor]+candidates
        name, path = find_binary_of_command([
            cls.compiler_dict[x] for x in candidates])
        if metadir and not used_metafile:
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
        return [self.compiler_binary] + self.flags + \
            ['-I'+x for x in self.inc_dirs] +\
            self.sources + \
            ['-L'+x for x in self.lib_dirs] +\
            ['-l'+x for x in self.libs]


    def run(self):
        if self.only_update:
            for src in self.sources:
                if missing_or_other_newer(self.out, src, cwd=self.cwd):
                    break
            else:
                self.logger.info(('No source newer than {}.'+\
                             ' Did not compile').format(
                                 self.out))
                return

        self.flags = uniquify(self.flags)

        # Append output flag and name to tail of flags
        self.flags.extend(['-o', self.out])

        # Logging
        if self.logger: self.logger.info(
                'Executing: "{}"'.format(' '.join(self.cmd)))

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
                ("Error executing '{}' in {}. "+\
                 "Command exited with status {}"+\
                 " after givning the following output: {}").format(
                     ' '.join(self.cmd), self.cwd, self.cmd_returncode,
                     str(self.cmd_outerr)))

        if self.logger and self.cmd_outerr: self.logger.info(
                '...with output:\n'+self.cmd_outerr)

        return self.cmd_outerr, self.cmd_returncode


class CCompilerRunner(CompilerRunner, HasMetaData):

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

class CppCompilerRunner(CompilerRunner, HasMetaData):

    compiler_dict = {
        'gnu': 'g++',
        'intel': 'icpc',
    }

    flag_dict = {
        'g++': {
            'c++11': ('-std=c++0x',),
        },
        'icpc': {
            'c++11': ('-std=c++11',),
        }
    }

    lib_dict = {
        'g++': {
            'fortran': ('gfortranbegin', 'gfortran'),
            'openmp': ('gomp',),
        },
        'icpc': {
            'openmp': ('iomp5',),
        }
    }

    compiler_name_vendor_mapping = {'g++': 'gnu', 'icpc': 'intel'}

    def __init__(self, *args, **kwargs):
        # g++ takes a superset of gcc arguments
        new_flag_dict = {
            'g++': CCompilerRunner.flag_dict['gcc'].copy(),
            'icpc': CCompilerRunner.flag_dict['icc'].copy(),
        }
        for key in ['g++', 'icpc']:
            fltr = _mk_flag_filter(key)
            keys, values = zip(*self.flag_dict[key].items())
            new_flag_dict[key].update(dict(zip(
                keys, filter(fltr, values))))
        self.flag_dict = new_flag_dict
        super(CppCompilerRunner, self).__init__(*args, **kwargs)


class FortranCompilerRunner(CompilerRunner, HasMetaData):

    compiler_dict = {
        'gnu': 'gfortran',
        'intel': 'ifort',
    }

    flag_dict = {
        'gfortran': {
            'f2008': ('-std=f2008',),
            'warn': ('-Wall', '-Wextra', '-Wimplicit-interface'),
        },
        'ifort': {
            'f2008': ('-stand f08',),
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
            'gfortran': CCompilerRunner.flag_dict['gcc'].copy(),
            'ifort': CCompilerRunner.flag_dict['icc'].copy(),
        }
        for key in ['gfortran', 'ifort']:
            new_flag_dict[key].update(self.flag_dict[key])
        self.flag_dict = new_flag_dict
        super(FortranCompilerRunner, self).__init__(*args, **kwargs)


def compile_sources(files, CompilerRunner_=None,
                    destdir=None, cwd=None,
                    update_only=True, **kwargs):
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
    -`update_only`: True (default) implies only to compile sources
        newer than their object files.
    -`**kwargs`: keyword arguments pass along to CompilerRunner_
    """
    destdir = destdir or '.'
    destdir = get_abspath(destdir, cwd=cwd)
    dstpaths = []
    for f in files:
        name, ext = os.path.splitext(os.path.basename(f))
        if CompilerRunner_ == None:
            if ext == '.c':
                CompilerRunner__ = CCompilerRunner
            elif ext in ('.cpp', '.cxx', '.cc'):
                CompilerRunner__ = CppCompilerRunner
            elif ext.lower() in ('.for', '.f', '.f90'):
                CompilerRunner__ = FortranCompilerRunner
            else:
                raise KeyError('Could not deduce compiler from" + \
                " extension: {}'.format(
                    ext))
        else:
            CompilerRunner__ = CompilerRunner_
        fname = name+'.o' # .ext -> .o
        dst = os.path.join(destdir, fname)
        dstpaths.append(dst)
        if missing_or_other_newer(dst, f, cwd=cwd):
            runner = CompilerRunner__(
                [f], dst, cwd=cwd, **kwargs)
            runner.run()
        else:
            msg = "Found {}, did not recompile.".format(dst)
            if 'logger' in kwargs:
                kwargs['logger'].info(msg)
            else:
                print(msg)
    return dstpaths


def compile_py_so(obj_files, CompilerRunner_=None,
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
    """
    libs = libs or []
    so_file = so_file or os.path.splitext(obj_files[-1])[0]+'.so'

    if not CompilerRunner_:
        if fort:
            CompilerRunner_, extra_kwargs, vendor = \
                get_mixed_fort_c_linker(
                    vendor=kwargs.get('vendor', None),
                    metadir=kwargs.get('metadir', None),
                    cplus=cplus
                )
            kwargs.update(extra_kwargs)
        else:
            if cplus:
                CompilerRunner_ = CppCompilerRunner
            else:
                CompilerRunner_ = CCompilerRunner

    from distutils.sysconfig import get_config_vars
    inc_dirs = kwargs.pop('inc_dirs', [])
    lib_dirs = kwargs.pop('lib_dirs', [])
    lds = filter(lambda x: len(x)>0, os.environ.get(
        'LD_LIBRARY_PATH', '').split(':'))
    lib_dirs.extend(lds)
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
                     **kwargs):
    from Cython.Compiler.Main import (
        default_options, compile, CompilationOptions
    )

    assert src.lower().endswith('.pyx') or src.lower().endswith('.py')
    cwd = cwd or '.'
    dstdir = dstdir or '.'

    ext = '.cpp' if kwargs['cplus'] else '.c'
    c_name = os.path.splitext(os.path.basename(src))[0] + ext

    dstfile = os.path.join(dstdir, c_name)

    if only_update:
        if not missing_or_other_newer(dstfile, src, cwd=cwd):
            logger.info(
                '{} newer than {}, did not re-cythonize.'.format(
                dstfile, src))
            return

    if cwd:
        ori_dir = os.getcwd()
    else:
        ori_dir = '.'
    os.chdir(cwd)

    cy_options = CompilationOptions(default_options)
    cy_options.__dict__.update(kwargs)
    if logger: logger.info("Cythonizing {} to {}".format(src, dstfile))
    compile([src], cy_options, full_module_name=full_module_name)
    if os.path.abspath(os.path.dirname(
            src)) != os.path.abspath(dstdir):
        if os.path.exists(dstfile):
            os.unlink(dstfile)
        shutil.move(os.path.join(os.path.dirname(src), c_name),
                    dstdir)
    os.chdir(ori_dir)


def _mk_flag_filter(cmplr_name):
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


def simple_py_c_compile_obj(src,
                            cplus=False,
                            **kwargs):
    """
    Use e.g. on *.c file written from `simple_cythonize`
    """
    from distutils.sysconfig import get_python_inc, get_config_vars
    inc_dirs = [get_python_inc()]
    inc_dirs.extend(kwargs.pop('inc_dirs',[]))

    if cplus:
        return cpp2obj(src, inc_dirs=inc_dirs, **kwargs)
    else:
        return c2obj(src, inc_dirs=inc_dirs, **kwargs)


def _src2obj(srcpath, CompilerRunner_, objpath=None, **kwargs):
    objpath = objpath or os.path.splitext(
        os.path.basename(srcpath))[0] + '.o'
    run_linker = kwargs.pop('run_linker', False)
    kwargs['options'] = kwargs.pop('options', ['pic', 'warn'])
    expand_collection_in_dict(kwargs, 'options',
                              kwargs.pop('extra_options', []))
    runner = CompilerRunner_([srcpath], objpath,
                             run_linker=run_linker, **kwargs)
    runner.run()
    return objpath


def fort2obj(srcpath, CompilerRunner_=FortranCompilerRunner,
          objpath=None, std=None, extra_options=None, **kwargs):
    """
    Convenience function
    """
    extra_options = extra_options or []
    extra_options.append(std or 'f2008')
    return _src2obj(srcpath, CompilerRunner_, objpath,
                    extra_options=extra_options, **kwargs)


def c2obj(srcpath, CompilerRunner_=CCompilerRunner,
          objpath=None, std=None, extra_options=None, **kwargs):
    """
    Convenience function
    """
    extra_options = extra_options or []
    extra_options.append(std or 'c99')
    return _src2obj(srcpath, CompilerRunner_, objpath,
                    extra_options=extra_options, **kwargs)


def cpp2obj(srcpath, CompilerRunner_=CppCompilerRunner,
          objpath=None, std=None, extra_options=None, **kwargs):
    """
    Convenience function
    """
    extra_options = extra_options or []
    extra_options.append(std or 'c++11')
    return _src2obj(srcpath, CompilerRunner_, objpath,
                    extra_options=extra_options, **kwargs)


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

    if os.path.isdir(objpath):
        pyx_fname = os.path.basename(pyxpath)
        objpath = os.path.join(objpath, pyx_fname[:-4]+'.o')

    interm_c_dir = interm_c_dir or os.path.dirname(objpath)
    abs_interm_c_dir = get_abspath(interm_c_dir, cwd=cwd)
    assure_dir(abs_interm_c_dir)

    ext = '.cpp' if cplus else '.c'
    interm_c_file = os.path.join(
        abs_interm_c_dir, os.path.basename(pyxpath)[:-4] + ext)

    cy_kwargs = cy_kwargs or {}
    cy_kwargs['output_dir'] = cwd
    cy_kwargs['cplus'] = cplus
    if gdb:
        cy_kwargs['gdb_debug'] = True

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

    flags = kwargs.pop('flags', [])
    flags.extend(['-fno-strict-aliasing'])
    return simple_py_c_compile_obj(
        interm_c_file, objpath=objpath, cwd=cwd, logger=logger,
        only_update=only_update, metadir=metadir,
        inc_dirs=inc_dirs, cplus=cplus, flags=flags, **kwargs)
