# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import

from collections import OrderedDict
import os
import re
import subprocess
import sys
import warnings

from .util import (
    HasMetaData, get_abspath, FileNotFoundError,
    find_binary_of_command, missing_or_other_newer,
    CompilationError,
)


class CompilerRunner(object):

    """
    CompilerRunner class.

    Parameters
    ==========
    sources: iterable of path strings
    out: path string
    flags: iterable of strings
    run_linker: bool
    compiler: string
        compiler command to call
    cwd: path string
        root of relative paths
    include_dirs: iterable of path strings
        include directories
    libraries: iterable of strings
        libraries to link against.
    library_dirs: iterable of path strings
        paths to search for shared libraries
    std: string
        Standard string, e.g. c++11, c99, f2008
    options: iterable of strings
        pycompilation convenience tags (fast, warn, pic, openmp).
        Sets extra compiler flags.
    define: iterable of strings
        macros to define
    undef: iterable of strings
        macros to undefine
    logger: logging.Logger
        info and error level used.
    preferred_vendor: string
        name of preferred vendor e.g. 'gnu' or 'intel'
    metadir: path string
        location where to cache metadata about compilation (choice of compiler)
    lib_options: iterable of strings
        pycompilation convenience tags e.g. 'openmp' and/or 'fortran'.
        Sets extra libraries.
    only_update: bool
        Only run compiler if sources are newer than destination. default: False

    Returns
    =======
    CompilerRunner instance

    Methods
    =======
    run():
        Invoke compilation as a subprocess. Log output if logger present.
    """

    compiler_dict = None  # Subclass to vendor/binary dict
    environ_key_ldflags = 'LDFLAGS'

    # Standards should be a tuple of supported standards
    # (first one will be the default)
    standards = None

    std_formater = None  # Subclass to dict of binary/formater-callback

    option_flag_dict = None  # Lazy unified defaults for compilers
    metadata_filename = '.metadata_CompilerRunner'

    # subclass to be e.g. {'gcc': 'gnu', ...}
    compiler_name_vendor_mapping = None

    logger = None

    default_compile_options = ('pic', 'warn')  # , 'fast'

    # http://software.intel.com/en-us/articles/intel-mkl-link-line-advisor
    # MKL 11.1 x86-64, *nix, MKLROOT env. set, dynamic linking
    # This is _really_ ugly and not portable in any manner.
    vendor_options_dict = {
        'intel': {
            'lapack': {
                'linkline': [],
                'libraries': ['mkl_avx', 'mkl_intel_lp64', 'mkl_core',
                              'mkl_intel_thread', 'pthread', 'm'],
                'library_dirs': ['${MKLROOT}/lib/intel64'],
                'include_dirs': ['${MKLROOT}/include/intel64/lp64',
                                 '${MKLROOT}/include'],
                'flags': ['-openmp'],
            } if os.environ.get("INTEL_MKL_DYNAMIC", False) else {
                'linkline': ['-Wl,--start-group ' +
                             ' ${MKLROOT}/lib/intel64/libmkl_intel_ilp64.a' +
                             ' ${MKLROOT}/lib/intel64/libmkl_core.a' +
                             ' ${MKLROOT}/lib/intel64/libmkl_intel_thread.a' +
                             ' -Wl,--end-group'],
                'libraries': ['pthread', 'm'],
                'library_dirs': ['${MKLROOT}/lib/intel64'],
                'include_dirs': ['${MKLROOT}/include'],
                'flags': ['-openmp'],
                'def_macros': ['MKL_ILP64'],
            }
        },
        'gnu': {
            'lapack': {
                'libraries': ['lapack', 'blas']
                }
            },
        'llvm': {
            'lapack': {
                'libraries': ['lapack', 'blas']
                }
            },
        }

    def __init__(self, sources, out, flags=None, run_linker=True,
                 compiler=None, cwd=None, include_dirs=None, libraries=None,
                 library_dirs=None, std=None, options=None, define=None,
                 undef=None, strict_aliasing=None, logger=None,
                 preferred_vendor=None, metadir=None, lib_options=None,
                 only_update=False, ldflags=None, **kwargs):

        cwd = cwd or '.'
        metadir = get_abspath(metadir or '.', cwd=cwd)

        if hasattr(sources, '__iter__'):
            self.sources = list(sources)
        else:
            self.sources = [sources]

        self.out = out
        self.flags = flags or []
        if os.environ.get(self.environ_key_flags):
            self.flags += os.environ[self.environ_key_flags].split()
        self.metadir = metadir
        self.cwd = cwd
        if compiler or os.environ.get(self.environ_key_compiler):
            if compiler:
                self.compiler_name, self.compiler_binary = compiler
            else:
                self.compiler_binary = os.environ[self.environ_key_compiler]
                for vk, cn in self.compiler_dict.items():
                    if cn in self.compiler_binary:
                        self.compiler_vendor = vk
                        self.compiler_name = cn
                        break
                else:
                    self.compiler_vendor, self.compiler_name = list(self.compiler_dict.items())[0]
                    warnings.warn("unsure of what kind of compiler %s is, assuming %s" %
                                  (self.compiler_binary, self.compiler_name))
            self.save_to_metadata_file(
                self.metadir, 'vendor',
                self.compiler_name_vendor_mapping[
                    self.compiler_name])
        else:
            # Find a compiler
            if preferred_vendor is None:
                preferred_vendor = os.environ.get('COMPILER_VENDOR', None)
            self.compiler_name, self.compiler_binary, \
                self.compiler_vendor = self.find_compiler(
                    preferred_vendor, metadir, self.cwd)
            if self.compiler_binary is None:
                raise RuntimeError(
                    "No compiler found (searched: {0})".format(
                        ', '.join(self.compiler_dict.values())))
        self.define = define or []
        self.undef = undef or []
        self.include_dirs = include_dirs or []
        self.libraries = libraries or []
        self.library_dirs = library_dirs or []
        self.options = options or self.default_compile_options
        self.std = std or self.standards[0]
        self.lib_options = lib_options or []
        self.logger = logger
        self.only_update = only_update
        self.run_linker = run_linker
        if self.run_linker:
            # both gnu and intel compilers use '-c' for disabling linker
            self.flags = list(filter(lambda x: x != '-c', self.flags))
        else:
            if '-c' not in self.flags:
                self.flags.append('-c')

        if self.std:
            self.flags.append(self.std_formater[
                self.compiler_name](self.std))

        self.linkline = (ldflags or []) + [lf for lf in map(
            str.strip, os.environ.get(self.environ_key_ldflags, "").split()) if lf != ""]

        # Handle options
        for opt in self.options:
            self.flags.extend(self.option_flag_dict.get(
                self.compiler_name, {}).get(opt, []))

            # extend based on vendor options dict
            def extend(l, k):
                l.extend(
                    self.vendor_options_dict.get(
                        self.compiler_vendor, {}).get(
                            opt, {}).get(k, []))
            for kw in ('flags', 'define', 'undef', 'include_dirs',
                       'library_dirs', 'libraries', 'linkline'):
                extend(getattr(self, kw), kw)

        # libraries
        for lib_opt in self.lib_options:
            self.libraries.extend(
                self.lib_dict[self.compiler_name][lib_opt])

        if strict_aliasing is not None:
            nsa_re = re.compile("no-strict-aliasing$")
            sa_re = re.compile("strict-aliasing$")
            if strict_aliasing is True:
                if any(map(nsa_re.match, flags)):
                    raise CompilationError("Strict aliasing cannot be" +
                                           " both enforced and disabled")
                elif any(map(sa_re.match, flags)):
                    pass  # already enforced
                else:
                    flags.append('-fstrict-aliasing')
            elif strict_aliasing is False:
                if any(map(nsa_re.match, flags)):
                    pass  # already disabled
                else:
                    if any(map(sa_re.match, flags)):
                        raise CompilationError("Strict aliasing cannot be" +
                                               " both enforced and disabled")
                    else:
                        flags.append('-fno-strict-aliasing')
            else:
                raise ValueError("Unknown strict_aliasing={}".format(
                    strict_aliasing))

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
                used_metafile = True
            except FileNotFoundError:
                pass
        candidates = list(cls.compiler_dict.keys())
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
            if cls.logger:
                cls.logger.info(
                    'Wrote choice of compiler to: metadir')
        return name, path, cls.compiler_name_vendor_mapping[name]

    def cmd(self):
        """
        The command below covers most cases, if you need
        someting more complex subclass this.
        """
        cmd = (
            [self.compiler_binary] +
            self.flags +
            ['-U'+x for x in self.undef] +
            ['-D'+x for x in self.define] +
            ['-I'+x for x in self.include_dirs] +
            self.sources
        )
        if self.run_linker:
            cmd += (['-L'+x for x in self.library_dirs] +
                    [(x if os.path.exists(x) else '-l'+x) for x in self.libraries] +
                    self.linkline)
        counted = []
        for envvar in re.findall('\$\{(\w+)\}', ' '.join(cmd)):
            if os.getenv(envvar) is None:
                if envvar not in counted:
                    counted.append(envvar)
                    msg = "Environment variable '{}' undefined.".format(
                        envvar)
                    self.logger.error(msg)
                    raise CompilationError(msg)
        return cmd

    def run(self):
        if self.only_update:
            for src in self.sources:
                if missing_or_other_newer(self.out, src, cwd=self.cwd):
                    break
            else:
                msg = ('No source newer than {0}.' +
                       ' Did not compile').format(
                           self.out)
                if self.logger:
                    self.logger.info(msg)
                else:
                    print(msg)
                return self.out

        # Append output flag and name to tail of flags
        self.flags.extend(['-o', self.out])

        # Logging
        if self.logger:
            self.logger.info(
                'In "{0}", executing:\n"{1}"'.format(
                    self.cwd, ' '.join(self.cmd())))

        env = os.environ.copy()
        env['PWD'] = self.cwd

        # NOTE: the ' '.join(self.cmd()) part seems to be necessary for
        # intel compilers
        p = subprocess.Popen(' '.join(self.cmd()),
                             shell=True,
                             cwd=self.cwd,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             env=env)
        comm = p.communicate()
        if sys.version_info[0] == 2:
            self.cmd_outerr = comm[0]
        else:
            try:
                self.cmd_outerr = comm[0].decode('utf-8')
            except UnicodeDecodeError:
                self.cmd_outerr = comm[0].decode('iso-8859-1')  # win32
        self.cmd_returncode = p.returncode

        # Error handling
        if self.cmd_returncode != 0:
            msg = "Error executing '{0}' in {1}. Command exited with" + \
                  " status {2} after givning the following output: {3}\n"
            raise CompilationError(msg.format(
                ' '.join(self.cmd()), self.cwd, str(self.cmd_returncode),
                self.cmd_outerr))

        if self.logger and len(self.cmd_outerr) > 0:
            self.logger.info('...with output:\n'+self.cmd_outerr)

        return self.cmd_outerr, self.cmd_returncode


class CCompilerRunner(CompilerRunner, HasMetaData):

    environ_key_compiler = 'CC'
    environ_key_flags = 'CFLAGS'

    compiler_dict = OrderedDict([
        ('gnu', 'gcc'),
        ('intel', 'icc'),
        ('llvm', 'clang'),
    ])

    standards = ('c89', 'c90', 'c99', 'c11')  # First is default

    std_formater = {
        'gcc': '-std={}'.format,
        'icc': '-std={}'.format,
        'clang': '-std={}'.format,
    }

    option_flag_dict = {
        'gcc': {
            'pic': ('-fPIC',),
            'warn': ('-Wall', '-Wextra'),
            # -march=native not portable and problematic for Mac OSX:
            'fast': ('-O2', '-ffast-math', '-funroll-loops'),
            'openmp': ('-fopenmp',),
            'debug': ('-g',),
        },
        'icc': {
            'pic': ('-fPIC',),
            'fast': ('-fast',),
            'openmp': ('-openmp',),
            'warn': ('-Wall',),
            'debug': ('-g',),
        },
        'clang': {
            'pic': ('-fPIC',),
            'warn': ('-Wall', '-Wextra'),
            'fast': ('-O2', '-ffast-math', '-funroll-loops'),
            'openmp': ('-fopenmp',),
            'debug': ('-g',),
        },
    }

    compiler_name_vendor_mapping = {
        'gcc': 'gnu',
        'icc': 'intel',
        'clang': 'llvm'
    }


def _mk_flag_filter(cmplr_name):  # helper for class initialization
    not_welcome = {'g++': ("Wimplicit-interface",)}  # "Wstrict-prototypes",)}
    if cmplr_name in not_welcome:
        def fltr(x):
            for nw in not_welcome[cmplr_name]:
                if nw in x:
                    return False
            return True
    else:
        def fltr(x):
            return True
    return fltr


class CppCompilerRunner(CompilerRunner, HasMetaData):

    environ_key_compiler = 'CXX'
    environ_key_flags = 'CXXFLAGS'

    compiler_dict = OrderedDict([
        ('gnu', 'g++'),
        ('intel', 'icpc'),
        ('llvm', 'clang++'),
    ])

    # First is the default, c++0x == c++11
    standards = ('c++98', 'c++0x')

    std_formater = {
        'g++': '-std={}'.format,
        'icpc': '-std={}'.format,
        'clang++': '-std={}'.format,
    }

    option_flag_dict = {
        'g++': {
        },
        'icpc': {
        },
        'clang++': {
        }
    }

    lib_dict = {
        'g++': {
            'fortran': ('gfortran',),
            'openmp': ('gomp',),
        },
        'icpc': {
            'openmp': ('iomp5',),
        },

    }

    compiler_name_vendor_mapping = {
        'g++': 'gnu',
        'icpc': 'intel',
        'clang++': 'llvm'
    }

    def __init__(self, *args, **kwargs):
        # g++ takes a superset of gcc arguments
        new_option_flag_dict = {
            'g++': CCompilerRunner.option_flag_dict['gcc'].copy(),
            'icpc': CCompilerRunner.option_flag_dict['icc'].copy(),
            'clang++': CCompilerRunner.option_flag_dict['clang'].copy(),
        }
        for key in ['g++', 'icpc', 'clang++']:
            if self.option_flag_dict[key]:
                fltr = _mk_flag_filter(key)
                keys, values = zip(*self.option_flag_dict[key].items())
                new_option_flag_dict[key].update(dict(zip(
                    keys, list(filter(fltr, values)))))
        self.option_flag_dict = new_option_flag_dict
        super(CppCompilerRunner, self).__init__(*args, **kwargs)


class FortranCompilerRunner(CompilerRunner, HasMetaData):

    environ_key_compiler = 'FC'
    environ_key_flags = 'FFLAGS'

    standards = (None, 'f95', 'f2003', 'f2008')  # First is default (F77)

    std_formater = {
        'gfortran': '-std={}'.format,
        'ifort': lambda x: '-stand f{}'.format(x[-2:]),  # f2008 => f08
    }

    compiler_dict = OrderedDict([
        ('gnu', 'gfortran'),
        ('intel', 'ifort'),
        ('llvm', 'gfortran')
    ])

    option_flag_dict = {
        'gfortran': {
            'warn': ('-Wall', '-Wextra', '-Wimplicit-interface'),
            'debug': ('-g',),
        },
        'ifort': {
            'warn': ('-warn', 'all',),
            'debug': ('-g',),
        },
    }

    lib_dict = {
        'gfortran': {
            'openmp': ('gomp',),
        },
        'ifort': {
            'openmp': ('iomp5',),
        },
    }

    compiler_name_vendor_mapping = {
        'gfortran': 'gnu',
        'ifort': 'intel',
    }

    def __init__(self, *args, **kwargs):
        # gfortran takes a superset of gcc arguments
        new_option_flag_dict = {
            'gfortran': CCompilerRunner.option_flag_dict['gcc'].copy(),
            'ifort': CCompilerRunner.option_flag_dict['icc'].copy(),
        }
        for key in ['gfortran', 'ifort']:
            new_option_flag_dict[key].update(self.option_flag_dict[key])
        self.option_flag_dict = new_option_flag_dict

        super(FortranCompilerRunner, self).__init__(*args, **kwargs)
