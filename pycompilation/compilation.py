# -*- coding: utf-8 -*-

"""
Motivation
==========

Distutils does not allow to use object files in compilation
(see http://bugs.python.org/issue5372)
hence the compilation of source files cannot be cached
unless doing something like what compile_sources / src2obj do.

Distutils does not support fortran out of the box (motivation of
numpy distutils), furthermore:
linking mixed C++/Fortran use either Fortran (Intel) or
C++ (GNU) compiler.
"""

from __future__ import print_function, division, absolute_import

import glob
import os
import shutil
import sys
import tempfile
import warnings

from .util import (
    MetaReaderWriter, missing_or_other_newer, get_abspath,
    expand_collection_in_dict, make_dirs, copy, Glob, ArbitraryDepthGlob,
    glob_at_depth, CompilationError, FileNotFoundError,
    import_module_from_file, pyx_is_cplus,
    md5_of_string, md5_of_file
)

from .runners import (
    CCompilerRunner,
    CppCompilerRunner,
    FortranCompilerRunner
)

from distutils.sysconfig import get_config_var

# if sys.version_info[0] == 2:  # python 2
sharedext = get_config_var('SO')
# else:
#    sharedext = get_config_var('EXT_SUFFIX')

if os.name == 'posix':  # Future improvement to make cross-platform
    # flagprefix = '-'
    objext = '.o'
elif os.name == 'nt':
    # flagprefix = '/' <-- let's assume mingw compilers...
    objext = '.obj'
else:
    raise ImportError("Unknown os.name: {}".format(os.name))


def get_mixed_fort_c_linker(vendor=None, metadir=None, cplus=False,
                            cwd=None):
    vendor = vendor or os.environ.get('COMPILER_VENDOR', None)

    if not vendor:
        metadir = get_abspath(metadir or '.', cwd=cwd)
        reader = MetaReaderWriter('.metadata_CompilerRunner')
        try:
            vendor = reader.get_from_metadata_file(metadir, 'vendor')
        except FileNotFoundError:
            vendor = None

    if vendor.lower() == 'intel':
        if cplus:
            return (FortranCompilerRunner,
                    {'flags': ['-nofor_main', '-cxxlib']}, vendor)
        else:
            return (FortranCompilerRunner,
                    {'flags': ['-nofor_main']}, vendor)
    elif vendor.lower() == 'gnu' or 'llvm':
        if cplus:
            return (CppCompilerRunner,
                    {'lib_options': ['fortran']}, vendor)
        else:
            return (FortranCompilerRunner,
                    {}, vendor)
    else:
        raise ValueError("No vendor found.")


def compile_sources(files, CompilerRunner_=None,
                    destdir=None, cwd=None,
                    keep_dir_struct=False,
                    per_file_kwargs=None,
                    **kwargs):
    """
    Compile source code files to object files.

    Parameters
    ----------
    files: iterable of path strings
        source files, if cwd is given, the paths are taken as relative.
    CompilerRunner_: CompilerRunner instance (optional)
        could be e.g. pycompilation.FortranCompilerRunner
        Will be inferred from filename extensions if missing.
    destdir: path string
        output directory, if cwd is given, the path is taken as relative
    cwd: path string
        working directory. Specify to have compiler run in other directory.
        also used as root of relative paths.
    keep_dir_struct: bool
        Reproduce directory structure in `destdir`. default: False
    per_file_kwargs: dict
        dict mapping instances in `files` to keyword arguments
    **kwargs: dict
        default keyword arguments to pass to CompilerRunner_
    """
    _per_file_kwargs = {}

    if per_file_kwargs is not None:
        for k, v in per_file_kwargs.items():
            if isinstance(k, Glob):
                for path in glob.glob(k.pathname):
                    _per_file_kwargs[path] = v
            elif isinstance(k, ArbitraryDepthGlob):
                for path in glob_at_depth(k.filename, cwd):
                    _per_file_kwargs[path] = v
            else:
                _per_file_kwargs[k] = v

    # Set up destination directory
    destdir = destdir or '.'
    if not os.path.isdir(destdir):
        if os.path.exists(destdir):
            raise IOError("{} is not a directory".format(destdir))
        else:
            make_dirs(destdir)
    if cwd is None:
        cwd = '.'
        for f in files:
            copy(f, destdir, only_update=True, dest_is_dir=True)

    # Compile files and return list of paths to the objects
    dstpaths = []
    for f in files:
        if keep_dir_struct:
            name, ext = os.path.splitext(f)
        else:
            name, ext = os.path.splitext(os.path.basename(f))
        file_kwargs = kwargs.copy()
        file_kwargs.update(_per_file_kwargs.get(f, {}))
        dstpaths.append(src2obj(
            f, CompilerRunner_, cwd=cwd,
            **file_kwargs
        ))
    return dstpaths


def link(obj_files, out_file=None, shared=False, CompilerRunner_=None,
         cwd=None, cplus=False, fort=False, **kwargs):
    """
    Link object files.

    Parameters
    ----------
    obj_files: iterable of path strings
    out_file: path string (optional)
        path to executable/shared library, if missing
        it will be deduced from the last item in obj_files.
    shared: bool
        Generate a shared library? default: False
    CompilerRunner_: pycompilation.CompilerRunner subclass (optional)
        If not given the `cplus` and `fort` flags will be inspected
        (fallback is the C compiler)
    cwd: path string
        root of relative paths and working directory for compiler
    cplus: bool
        C++ objects? default: False
    fort: bool
        Fortran objects? default: False
    **kwargs: dict
        keyword arguments passed onto CompilerRunner_

    Returns
    -------
    The absolute to the generated shared object / executable

    """
    if out_file is None:
        out_file, ext = os.path.splitext(os.path.basename(obj_files[-1]))
        if shared:
            out_file += sharedext

    if not CompilerRunner_:
        if fort:
            CompilerRunner_, extra_kwargs, vendor = \
                get_mixed_fort_c_linker(
                    vendor=kwargs.get('vendor', None),
                    metadir=kwargs.get('metadir', None),
                    cplus=cplus,
                    cwd=cwd,
                )
            for k, v in extra_kwargs.items():
                expand_collection_in_dict(kwargs, k, v)
        else:
            if cplus:
                CompilerRunner_ = CppCompilerRunner
            else:
                CompilerRunner_ = CCompilerRunner

    flags = kwargs.pop('flags', [])
    if shared:
        if '-shared' not in flags:
            flags.append('-shared')

        # mimic GNU linker behavior on OS X when using -shared
        # (otherwise likely Undefined symbol errors)
        dl_flag = '-undefined dynamic_lookup'
        if sys.platform == 'darwin' and dl_flag not in flags:
            flags.append(dl_flag)
    run_linker = kwargs.pop('run_linker', True)
    if not run_linker:
        raise ValueError("link(..., run_linker=False)!?")

    out_file = get_abspath(out_file, cwd=cwd)
    runner = CompilerRunner_(
        obj_files, out_file, flags,
        cwd=cwd,
        **kwargs)
    runner.run()
    return out_file


def link_py_so(obj_files, so_file=None, cwd=None, libraries=None,
               cplus=False, fort=False, **kwargs):
    """
    Link python extension module (shared object) for importing

    Parameters
    ----------
    obj_files: iterable of path strings
        object files to be linked
    so_file: path string
        Name (path) of shared object file to create. If
        not specified it will have the basname of the last object
        file in `obj_files` but with the extension '.so' (Unix) or
        '.dll' (Windows).
    cwd: path string
        root of relative paths and working directory of linker.
    libraries: iterable of strings
        libraries to link against, e.g. ['m']
    cplus: bool
        Any C++ objects? default: False
    fort: bool
        Any Fortran objects? default: False
    kwargs**: dict
        keyword arguments passed onto `link(...)`

    Returns
    -------
    Absolute path to the generate shared object
    """
    libraries = libraries or []

    include_dirs = kwargs.pop('include_dirs', [])
    library_dirs = kwargs.pop('library_dirs', [])
    # from distutils/command/build_ext.py:
    if sys.platform == "win32":
        warnings.warn("Windows not yet supported.")
    elif sys.platform == 'darwin':
        # Don't use the default code below
        pass
    elif sys.platform[:3] == 'aix':
        # Don't use the default code below
        pass
    elif get_config_var('Py_ENABLE_SHARED'):
        # LIBDIR/INSTSONAME should always points to libpython (dynamic or static)
        pylib = os.path.join(get_config_var('LIBDIR'), get_config_var('INSTSONAME'))
        if os.path.exists(pylib):
            libraries.append(pylib)
        else:
            ABIFLAGS = get_config_var('ABIFLAGS')
            pythonlib = 'python{}.{}{}'.format(
                sys.hexversion >> 24, (sys.hexversion >> 16) & 0xff,
                ABIFLAGS or '')
            libraries += [pythonlib]

    flags = kwargs.pop('flags', [])
    needed_flags = ('-pthread',)
    for flag in needed_flags:
        if flag not in flags:
            flags.append(flag)

    # We want something like: gcc, ['-pthread', ...
    # compilername, flags = cc.split()[0], cc.split()[1:]

    # # Grab include_dirs
    # include_dirs += list(filter(lambda x: x.startswith('-I'), flags))
    # flags = list(filter(lambda x: not x.startswith('-I'), flags))

    # # Grab library_dirs
    # library_dirs += [x[2:] for x in filter(
    #     lambda x: x.startswith('-L'), flags)]
    # flags = list(filter(lambda x: not x.startswith('-L'), flags))

    # flags.extend(kwargs.pop('flags', []))

    return link(obj_files, shared=True, flags=flags, cwd=cwd,
                cplus=cplus, fort=fort, include_dirs=include_dirs,
                libraries=libraries, library_dirs=library_dirs, **kwargs)


def simple_cythonize(src, destdir=None, cwd=None, logger=None,
                     full_module_name=None, only_update=False,
                     **cy_kwargs):
    """
    Generates a C file from a Cython source file.

    Parameters
    ----------
    src: path string
        path to Cython source
    destdir: path string (optional)
        Path to output directory (default: '.')
    cwd: path string (optional)
        Root of relative paths (default: '.')
    logger: logging.Logger
        info level used.
    full_module_name: string
        passed to cy_compile (default: None)
    only_update: bool
        Only cythonize if source is newer. default: False
    **cy_kwargs:
        second argument passed to cy_compile.
        Generates a .cpp file if cplus=True in cy_kwargs, else a .c file.
    """
    from Cython.Compiler.Main import (
        default_options, CompilationOptions
    )
    from Cython.Compiler.Main import compile as cy_compile

    assert src.lower().endswith('.pyx') or src.lower().endswith('.py')
    cwd = cwd or '.'
    destdir = destdir or '.'

    ext = '.cpp' if cy_kwargs.get('cplus', False) else '.c'
    c_name = os.path.splitext(os.path.basename(src))[0] + ext

    dstfile = os.path.join(destdir, c_name)

    if only_update:
        if not missing_or_other_newer(dstfile, src, cwd=cwd):
            msg = '{0} newer than {1}, did not re-cythonize.'.format(
                dstfile, src)
            if logger:
                logger.info(msg)
            else:
                print(msg)
            return dstfile

    if cwd:
        ori_dir = os.getcwd()
    else:
        ori_dir = '.'
    os.chdir(cwd)
    try:
        cy_options = CompilationOptions(default_options)
        cy_options.__dict__.update(cy_kwargs)
        if logger:
            logger.info("Cythonizing {0} to {1}".format(
                src, dstfile))
        cy_result = cy_compile([src], cy_options, full_module_name=full_module_name)
        if cy_result.num_errors > 0:
            raise ValueError("Cython compilation failed.")
        if os.path.abspath(os.path.dirname(
                src)) != os.path.abspath(destdir):
            if os.path.exists(dstfile):
                os.unlink(dstfile)
            shutil.move(os.path.join(os.path.dirname(src), c_name),
                        destdir)
    finally:
        os.chdir(ori_dir)
    return dstfile


extension_mapping = {
    '.c': (CCompilerRunner, None),
    '.cpp': (CppCompilerRunner, None),
    '.cxx': (CppCompilerRunner, None),
    '.f': (FortranCompilerRunner, None),
    '.for': (FortranCompilerRunner, None),
    '.ftn': (FortranCompilerRunner, None),
    '.f90': (FortranCompilerRunner, 'f2008'),  # ifort only knows about .f90
    '.f95': (FortranCompilerRunner, 'f95'),
    '.f03': (FortranCompilerRunner, 'f2003'),
    '.f08': (FortranCompilerRunner, 'f2008'),
}


def src2obj(srcpath, CompilerRunner_=None, objpath=None,
            only_update=False, cwd=None, out_ext=None, inc_py=False,
            **kwargs):
    """
    Compiles a source code file to an object file.
    Files ending with '.pyx' assumed to be cython files and
    are dispatched to pyx2obj.

    Parameters
    ----------
    srcpath: path string
        path to source file
    CompilerRunner_: pycompilation.CompilerRunner subclass (optional)
        Default: deduced from extension of srcpath
    objpath: path string (optional)
        path to generated object. defualt: deduced from srcpath
    only_update: bool
        only compile if source is newer than objpath. default: False
    cwd: path string (optional)
        working directory and root of relative paths. default: current dir.
    out_ext: string
        set when objpath is a dir and you want to override defaults
        ('.o'/'.obj' for Unix/Windows).
    inc_py: bool
        add Python include path to include_dirs. default: False
    **kwargs: dict
        keyword arguments passed onto CompilerRunner_ or pyx2obj
    """
    name, ext = os.path.splitext(os.path.basename(srcpath))
    if objpath is None:
        if os.path.isabs(srcpath):
            objpath = '.'
        else:
            objpath = os.path.dirname(srcpath)
            objpath = objpath or '.'  # avoid objpath == ''
    out_ext = out_ext or objext
    if os.path.isdir(objpath):
        objpath = os.path.join(objpath, name+out_ext)

    include_dirs = kwargs.pop('include_dirs', [])
    if inc_py:
        from distutils.sysconfig import get_python_inc
        py_inc_dir = get_python_inc()
        if py_inc_dir not in include_dirs:
            include_dirs.append(py_inc_dir)

    if ext.lower() == '.pyx':
        return pyx2obj(srcpath, objpath=objpath,
                       include_dirs=include_dirs, cwd=cwd,
                       only_update=only_update, **kwargs)

    if CompilerRunner_ is None:
        CompilerRunner_, std = extension_mapping[ext.lower()]
        if 'std' not in kwargs:
            kwargs['std'] = std

    # src2obj implies not running the linker...
    run_linker = kwargs.pop('run_linker', False)
    if run_linker:
        raise CompilationError("src2obj called with run_linker=True")

    if only_update:
        if not missing_or_other_newer(objpath, srcpath, cwd=cwd):
            msg = "Found {0}, did not recompile.".format(objpath)
            if kwargs.get('logger', None):
                kwargs['logger'].info(msg)
            else:
                print(msg)
            return objpath
    runner = CompilerRunner_(
        [srcpath], objpath, include_dirs=include_dirs,
        run_linker=run_linker, cwd=cwd, **kwargs)
    runner.run()
    return objpath


def pyx2obj(pyxpath, objpath=None, interm_c_dir=None, cwd=None,
            logger=None, full_module_name=None, only_update=False,
            metadir=None, include_numpy=False, include_dirs=None,
            cy_kwargs=None, gdb=False, cplus=None, **kwargs):
    """
    Convenience function

    If cwd is specified, pyxpath and dst are taken to be relative
    If only_update is set to `True` the modification time is checked
    and compilation is only run if the source is newer than the
    destination

    Parameters
    ----------
    pyxpath: path string
        path to Cython source file
    objpath: path string (optional)
        path to object file to generate
    interm_c_dir: path string (optional)
        directory to put generated C file.
    cwd: path string (optional)
        working directory and root of relative paths
    logger: logging.Logger (optional)
        passed onto `simple_cythonize` and `src2obj`
    full_module_name: string (optional)
        passed onto `simple_cythonize`
    only_update: bool (optional)
        passed onto `simple_cythonize` and `src2obj`
    metadir: path string (optional)
        passed onto src2obj
    include_numpy: bool (optional)
        Add numpy include directory to include_dirs. default: False
    include_dirs: iterable of path strings (optional)
        Passed onto src2obj and via cy_kwargs['include_path']
        to simple_cythonize.
    cy_kwargs: dict (optional)
        keyword arguments passed onto `simple_cythonize`
    gdb: bool (optional)
        convenience: cy_kwargs['gdb_debug'] is set True if gdb=True,
        default: False
    cplus: bool (optional)
        Indicate whether C++ is used. default: auto-detect using `pyx_is_cplus`
    **kwargs: dict
        keyword arguments passed onto src2obj

    Returns
    -------
    Absolute path of generated object file.

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
    if cplus is None:
        cplus = pyx_is_cplus(pyxpath)
    cy_kwargs['cplus'] = cplus
    if gdb:
        cy_kwargs['gdb_debug'] = True
    if include_dirs:
        cy_kwargs['include_path'] = include_dirs

    interm_c_file = simple_cythonize(
        pyxpath, destdir=interm_c_dir,
        cwd=cwd, logger=logger,
        full_module_name=full_module_name,
        only_update=only_update, **cy_kwargs)

    include_dirs = include_dirs or []
    if include_numpy:
        import numpy
        numpy_inc_dir = numpy.get_include()
        if numpy_inc_dir not in include_dirs:
            include_dirs.append(numpy_inc_dir)

    flags = kwargs.pop('flags', [])
    needed_flags = ('-fwrapv', '-pthread')
    if not cplus:
        needed_flags += ('-Wstrict-prototypes',)  # not really needed..
    for flag in needed_flags:
        if flag not in flags:
            flags.append(flag)

    options = kwargs.pop('options', [])

    if kwargs.pop('strict_aliasing', False):
        raise CompilationError("Cython req. strict aliasing to be disabled.")

    if 'pic' not in options:
        options.append('pic')
    if 'warn' not in options:
        options.append('warn')

    # Let's be explicit about standard
    if cplus:
        std = kwargs.pop('std', 'c++98')
    else:
        std = kwargs.pop('std', 'c99')

    return src2obj(
        interm_c_file,
        objpath=objpath,
        cwd=cwd,
        only_update=only_update,
        metadir=metadir,
        include_dirs=include_dirs,
        flags=flags,
        std=std,
        options=options,
        logger=logger,
        inc_py=True,
        strict_aliasing=False,
        **kwargs)


def _any_X(srcs, cls):
    for src in srcs:
        name, ext = os.path.splitext(src)
        key = ext.lower()
        if key in extension_mapping:
            if extension_mapping[key][0] == cls:
                return True
    return False


def any_fort(srcs):
    return _any_X(srcs, FortranCompilerRunner)


def any_cplus(srcs):
    return _any_X(srcs, CppCompilerRunner)


def compile_link_import_py_ext(
        srcs, extname=None, build_dir=None, compile_kwargs=None,
        link_kwargs=None, **kwargs):
    """
    Compiles sources in `srcs` to a shared object (python extension)
    which is imported. If shared object is newer than the sources, they
    are not recompiled but instead it is imported.

    Parameters
    ----------
    srcs: string
        list of paths to sources
    extname: string
        name of extension (default: None)
        (taken from the last file in `srcs` - without extension)
    build_dir: string
        path to directory in which objects files etc. are generated
    compile_kwargs: dict
        keyword arguments passed to compile_sources
    link_kwargs: dict
        keyword arguments passed to link_py_so
    **kwargs:
        additional keyword arguments overwrites to both compile_kwargs
        and link_kwargs useful for convenience e.g. when passing logger

    Returns
    -------
    the imported module

    Examples
    --------
    >>> mod = compile_link_import_py_ext(['fft.f90', 'convolution.cpp',\
        'fft_wrapper.pyx'], only_update=True)  # doctest: +SKIP
    >>> Aprim = mod.fft(A)  # doctest: +SKIP

    """

    build_dir = build_dir or '.'
    if extname is None:
        extname = os.path.splitext(os.path.basename(srcs[-1]))[0]

    compile_kwargs = compile_kwargs or {}
    compile_kwargs.update(kwargs)

    link_kwargs = link_kwargs or {}
    link_kwargs.update(kwargs)

    try:
        mod = import_module_from_file(os.path.join(build_dir, extname), srcs)
    except ImportError:
        objs = compile_sources(list(map(get_abspath, srcs)), destdir=build_dir,
                               cwd=build_dir, **compile_kwargs)
        so = link_py_so(
            objs, cwd=build_dir, fort=any_fort(srcs), cplus=any_cplus(srcs),
            **link_kwargs)
        mod = import_module_from_file(so)
    return mod


def compile_link_import_strings(codes, build_dir=None, **kwargs):
    """
    Creates a temporary directory and dumps, compiles and links
    provided source code.

    Parameters
    ----------
    codes: iterable of name/source pair tuples
    build_dir: string (default: None)
        path to cache_dir. None implies use a temporary directory.
    **kwargs:
        keyword arguments passed onto `compile_link_import_py_ext`
    """
    build_dir = build_dir or tempfile.mkdtemp()
    if not os.path.isdir(build_dir):
        raise OSError("Non-existent directory: ", build_dir)

    source_files = []
    if kwargs.get('logger', False) is True:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        kwargs['logger'] = logging.getLogger()

    only_update = kwargs.get('only_update', True)
    for name, code_ in codes:
        dest = os.path.join(build_dir, name)
        differs = True
        md5_in_mem = md5_of_string(code_.encode('utf-8')).hexdigest()
        if only_update and os.path.exists(dest):
            if os.path.exists(dest+'.md5'):
                md5_on_disk = open(dest+'.md5', 'rt').read()
            else:
                md5_on_disk = md5_of_file(dest).hexdigest()
            differs = md5_on_disk != md5_in_mem
        if not only_update or differs:
            with open(dest, 'wt') as fh:
                fh.write(code_)
                open(dest+'.md5', 'wt').write(md5_in_mem)
        source_files.append(dest)

    return compile_link_import_py_ext(
        source_files, build_dir=build_dir, **kwargs)
