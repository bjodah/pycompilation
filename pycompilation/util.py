import os
import pickle
from hashlib import md5

from mako.template import Template
from mako.exceptions import text_error_template


def run_sub_setup(cwd, cb, logger):
    """
    Useful for calling in a setup.py script
    see symodesys's setup.py for an example
    """
    ori_dir = os.path.abspath(os.curdir)
    os.chdir(cwd)
    cb(cwd, logger)
    os.chdir(ori_dir)


def render_mako_template_to(template, outpath, subsd):
    """
    template: either string of path or file like obj.
    """
    if hasattr(template, 'read'):
        # set in-file handle to provided template
        ifh = template
    else:
        # Assume template is a string of the path to the template
        ifh = open(template, 'rt')

    template_str = ifh.read()
    with open(outpath, 'wt') as ofh:
        try:
            rendered = Template(template_str).render(**subsd)
        except:
            print(text_error_template().render())
            raise

        ofh.write(rendered)



def md5_of_file(path):
    """
    Use .digest() or .hexdigest() on returned object
    to get binary or hex encoded string.
    """
    md = md5()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(128*md.block_size), b''):
             md.update(chunk)
    return md


def missing_or_other_newer(path, other_path):
    if not os.path.exists(path):
        return True
    if os.path.getmtime(other_path) > os.path.getmtime(path):
        return True
    return False


class HasMetaData(object):
    """
    Provides convenice methods for a class to pickle some metadata
    """
    metadata_filename = '.metadata'

    @classmethod
    def _get_metadata_key(cls, kw):
        """ kw could be e.g. 'compiler' """
        return cls.__name__+'_'+kw


    @classmethod
    def get_from_metadata_file(cls, dirpath, key):
        """
        Get value of key in metadata file dict.
        """
        fullpath = os.path.join(dirpath, cls.metadata_filename)
        if os.path.exists(fullpath):
            d = pickle.load(open(fullpath,'r'))
            return d[key] #.get(cls._get_metadata_key(key), None)
        else:
            raise IOError("No such file: {}".format(fullpath))

    @classmethod
    def save_to_metadata_file(cls, dirpath, key, value):
        """
        Store `key: value` in metadata file dict.
        """
        fullpath = os.path.join(dirpath, cls.metadata_filename)
        if os.path.exists(fullpath):
            d = pickle.load(open(fullpath,'r'))
            d.update({key: value})
            pickle.dump(d, open(fullpath,'w'))
        else:
            pickle.dump({key: value}, open(fullpath,'w'))


def import_(filename):
    """
    Imports (cython generated) shared object file (.so)

    Warning, Python's caching or the OS caching (unclear to author)
    is horrible for reimporting same path of an .so file. It will
    not detect the new time stamp nor new checksum but will use old
    module.

    Use unique names for this reason
    """
    import imp
    path, name = os.path.split(filename)
    name, ext = os.path.splitext(name)
    fobj, filename, data = imp.find_module(name, [path])
    mod = imp.load_module(name, fobj, filename, data)
    return mod


def download_files(websrc, files, md5sums, cwd=None, only_if_missing=True):
        # Download sources ----------------------------------------
    for f in files:
        fpath = os.path.join(cwd, f) if cwd else f
        if not os.path.exists(fpath):
            import urllib2
            print('Downloading: {}'.format(websrc+f))
            open(fpath, 'wt').write(urllib2.urlopen(websrc+f).read())
        fmd5 = md5_of_file(fpath).hexdigest()
        if fmd5 != md5sums[f]:
            raise ValueError("""Warning: MD5 sum of {} differs from that provided in setup.py.
            i.e. {} vs. {}""".format(f, fmd5, md5sums[f]))


def compile_sources(CompilerRunner_, files, destdir=None, cwd=None,
                    update_only=True, **kwargs):
    """
    Distutils does not allow to use .o files in compilation
    (see http://bugs.python.org/issue5372)
    hence the compilation of source files cannot be cached
    unless doing something like what compile_sources does.

    Arguments:
    -`CompilerRunner_`: coulde be e.g. pycompilation.FortranCompilerRunner
    -`files`: list of paths to source files, if cwd is given, the paths are taken as relative
    -`destdir`: path to output directory, if cwd is given, the path is taken as relative
    -`cwd`: current working directory. Specify to have compiler run in other directory.
    -`update_only`: True (default) implies only to compile sources newer than their object files.
    -`**kwargs`: keyword arguments pass along to CompilerRunner_
    """
    destdir = destdir or '.'
    for f in files:
        name, ext = os.path.splitext(f)
        fname = name+'.o' # .ext -> .o
        if cwd:
            dst = os.path.join(cwd, destdir, fname)
        else:
            dst = os.path.join(destdir, fname)
        if missing_or_other_newer(dst, f):
            runner = CompilerRunner_(
                [f], dst, cwd=cwd, **kwargs)
            runner.run()
        else:
            print("Found {}, did not recompile.".format(dst))


def compile_py_so(CompilerRunner_, obj_files, so_file, cwd=None,
                  inc_dirs=None, libs=None, lib_dirs=None,
                  preferred_vendor=None, logger=None):
    """
    Generate shared object for importing
    """
    from distutils.sysconfig import get_config_vars
    pylibs = [x[2:] for x in get_config_vars(
        'BLDLIBRARY')[0].split() if x.startswith('-l')]
    cc = get_config_vars('BLDSHARED')[0]

    inc_dirs = inc_dirs or []
    libs = libs or []
    lib_dirs = lib_dirs or []

    # We want something like: gcc, ['-pthread', ...
    compilername, flags = cc.split()[0], cc.split()[1:]
    runner = CompilerRunner_(
        obj_files,
        so_file, flags,
        cwd=cwd,
        inc_dirs=inc_dirs,
        libs=libs+pylibs,
        lib_dirs=lib_dirs,
        preferred_vendor=preferred_vendor,
        logger=logger)
    runner.run()
