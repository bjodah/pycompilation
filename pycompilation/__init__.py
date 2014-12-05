__version__ = '0.4.0'

from .compilation import (
    compile_sources, link_py_so, src2obj,
    compile_link_import_py_ext, compile_link_import_strings
)
from .util import (
    missing_or_other_newer, md5_of_file,
    import_module_from_file, CompilationError, FileNotFoundError
)
