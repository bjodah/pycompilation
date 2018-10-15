"""
pycompilation is a package for meta programming. It aims to support
multiple compilers: GNU, Intel, PGI.
"""

from ._release import __version__

from .compilation import (
    compile_sources, link_py_so, src2obj,
    compile_link_import_py_ext, compile_link_import_strings
)

from .util import (
    missing_or_other_newer, md5_of_file,
    import_module_from_file, CompilationError, FileNotFoundError
)
