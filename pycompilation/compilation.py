from __future__ import print_function, division

import os
import subprocess

from distutils.spawn import find_executable

from helpers import HasMetaData, missing_or_other_newer
# TODO: change print statements to logging statements.


class CompilationError(Exception):
    pass


def find_binary_of_command(candidates):
    """
    Currently only support *nix systems (invocation of which)
    """
    for c in candidates:
        binary_path = find_executable(c)
        if c:
            return c, binary_path
    raise RuntimeError('No binary located for candidates: {}'.format(
        candidates))



def _uniquify(l):
    result = []
    for x in l:
        if not x in result:
            result.append(x)
    return result

def simple_cythonize(src, cwd=None, logger=None, full_module_name=None, only_update=False):
    from Cython.Compiler.Main import (
        default_options, compile, CompilationOptions
    )
    if cwd:
        src = os.path.join(cwd, src)
    dst = os.path.splitext(src)[0] + '.c'

    if only_update:
        if not missing_or_other_newer(dst, src):
            logger.info('{} newer than {}, did not compile'.format(
                dst, src))
            return
    cy_options = CompilationOptions(default_options)
    if logger: logger.info("Cythonizing {} to {}".format(src, dst))
    compile([src], cy_options, full_module_name=full_module_name)


def simple_py_c_compile_obj(src, dst=None, cwd=None, logger=None, only_update=False):
    """
    Use e.g. on *.c file written from `simple_cythonize`
    """
    dst = dst or os.path.splitext(src)[0] + '.o'
    if only_update:
        if not missing_or_other_newer(dst, src):
            logger.info('{} newer than {}, did not compile'.format(
                dst, src))
            return

    from distutils.sysconfig import get_python_inc, get_config_vars
    import numpy
    includes = [get_python_inc(), numpy.get_include()]
    cc = " ".join(get_config_vars('CC', 'BASECFLAGS', 'OPT', 'CFLAGSFORSHARED'))
    compilern, flags = cc.split()[0], cc.split()[1:]
    runner =CCompilerRunner([src], dst, flags, run_linker=False,
                            compiler=[compilern]*2, cwd=cwd,
                            inc_dirs=includes, logger=logger)
    return runner.run() # outerr, returncode


def pyx2obj(pyxpath, dst=None, cwd=None, logger=None, full_module_name=None, only_update=False):
    """
    Conveninece function

    If cwd is specified, pyxpath and dst are taken to be relative
    If only_update is set to `True` the modification time is checked
    and compilation is only run if the source is newer than the destination
    """
    if cwd:
        pyxpath = os.path.join(cwd, pyxpath)
        dst = os.path.join(cwd, dst)
    assert pyxpath.endswith('.pyx')
    simple_cythonize(pyxpath, cwd=cwd, logger=logger,
                     full_module_name=full_module_name, only_update=only_update)
    simple_py_c_compile_obj(pyxpath[:-4]+'.c', dst=dst, cwd=cwd, logger=logger,
                            only_update=only_update)


class CompilerRunner(HasMetaData):

    flag_dict = None # Lazy unified defaults for compilers
    metadata_filename = '.metadata_CompilerRunner'

    def __init__(self, sources, out, flags=None, run_linker=True,
                 compiler=None, cwd=None, inc_dirs=None, libs=None,
                 lib_dirs=None,
                 options=None, logger=None, preferred_vendor=None,
                 metadir=None):
        """
        Arguments:
        - `preferred_vendor`: key of compiler_dict
        """

        self.sources = sources if hasattr(sources,'__iter__') else [sources]
        self.out = out
        self.flags = flags or []
        #self.run_linker = run_linker
        if compiler:
            self.compiler_name, self.compiler_binary = compiler
        else:
            # Find a compiler

            preferred_compiler_name = self.compiler_dict.get(preferred_vendor,None)
            self.compiler_name, self.compiler_binary = self.find_compiler(
                preferred_compiler_name, metadir or cwd)
            if self.compiler_binary == None:
                raise RuntimeError("No compiler found (searched: {})".format(
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
    def find_compiler(cls, preferred_compiler_name=None, load_save_choice=None):
        """
        Identify a suitable C/fortran/other compiler

        When it is possible that the user (un)installs a compiler inbetween
        compilations of object files we want to catch that. This method
        allows compiler choice to be stored in a pickled metadata file.
        Provide load_save_choice a dirpath to make the class save choice
        there in a file with cls.metadata_filename as name.
        """
        if load_save_choice:
            try:
                return cls.get_from_metadata_file(load_save_choice, 'compiler')
            except IOError:
                pass
        candidates = cls.flag_dict.keys()
        if preferred_compiler_name:
            if preferred_compiler_name in candidates:
                # Duplication doesn't matter
                candidates = [preferred_compiler_name] + candidates
        name_path = find_binary_of_command(candidates)
        if load_save_choice:
            cls.save_to_metadata_file(load_save_choice, 'compiler', name_path)
        return name_path


    def run(self):
        self.flags = _uniquify(self.flags)

        # Append output flag and name to tail of flags
        self.flags.extend(['-o', self.out])

        self.cmd = [self.compiler_binary]+self.flags+self.sources+['-l'+x for x in self.libs]
        # Logging
        if self.logger: self.logger.info('Executing: "{}"'.format(' '.join(self.cmd)))

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
                ("Error executing '{}' in {}. Commanded exited with status {}"+\
                 " after givning the following output: {}").format(
                     ' '.join(self.cmd), self.cwd, self.cmd_returncode, str(self.cmd_outerr)))

        if self.logger: self.logger.info('...with output: '+self.cmd_outerr)

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
            'fast': ('-O3', '-march=native', '-ffast-math', '-funroll-loops'),
        },
        'icc': {
            'pic': ('-fPIC',),
            'fast': ('-fast',),
        }
    }


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
            'f90': ('-stand f95',),
            'warn': ('-warn', 'all',),
        }
    }


    def __init__(self, *args, **kwargs):
        # gfortran takes a superset of gcc arguments
        new_flag_dict = {'gfortran': CCompilerRunner.flag_dict['gcc'],
                         'ifort': CCompilerRunner.flag_dict['icc'],
                         }
        for key in ['gfortran', 'ifort']:
            new_flag_dict[key].update(self.flag_dict[key])
        self.flag_dict = new_flag_dict
        super(FortranCompilerRunner, self).__init__(*args, **kwargs)
