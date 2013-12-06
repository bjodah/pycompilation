import os
import pickle
import shutil
from hashlib import md5

from mako.template import Template
from mako.exceptions import text_error_template


def term_fmt(s, fg=('red','black')):
    """
    See http://ascii-table.com/ansi-escape-sequences.php
    """
    fgi = {
        'black': 30,
        'red': 31,
        'green': 32,
        'yellow': 33,
        'blue': 34,
        'magenta': 35,
        'cyan': 36,
        'white': 37,
        }
    return '\033[{};1m'.format(fgi[fg[0].lower()])+\
        s+ '\033[{};0m'.format(fgi[fg[1].lower()])


def get_abspath(path, cwd=None):
    if os.path.isabs(path):
        return path
    else:
        cwd = cwd or '.'
        return os.path.abspath(
            os.path.join(cwd, path)
        )

def copy(src, dst, only_update=False, copystat=True):
    """
    shutil.copy with an `only_update` option
    """
    if not os.path.exists(src):
        # Source needs to exist
        msg = "`{}` does not exist".format(src)
        print(msg) # distutils just spits out `error: None`
        raise IOError(msg)
    if os.path.exists(dst):
        if os.path.isfile(dst):
            pass
        elif os.path.isdir(dst):
            dst = os.path.join(dst, os.path.basename(src))
        else:
            raise NotImplementedError
    else:
        if dst[-1] == '/':
            msg = "You must create directory first."
            print(msg) # distutils just spits out `error: None`
            raise IOError(msg)
        else:
            if not os.path.exists(os.path.dirname(dst[:-1])):
                msg = "You must create directory first."
                print(msg) # distutils just spits out `error: None`
                raise IOError(msg)
    if only_update:
        if not missing_or_other_newer(src, dst):
            return
    shutil.copy(src, dst)
    if copystat:
        shutil.copystat(src, dst)


def run_sub_setup(cb, destdir, **kwargs):
    """
    Useful for calling in a setup.py script
    see symodesys's setup.py for an example

    Pass keyword arg. `cwd` to execute in other
    directory.
    """
    ori_dir = os.path.abspath(os.curdir)
    os.chdir(kwargs.get('cwd', '.'))
    assert os.path.isdir(destdir)
    cb(destdir, **kwargs)
    os.chdir(ori_dir)


def render_mako_template_to(template, outpath, subsd,
                            only_update=False, cwd=None,
                            prev_subsd=None):
    """
    template: either string of path or file like obj.

    Beware of the only_update option, it pays no attention to
    an updated subsd.
    """
    if cwd:
        template = os.path.join(cwd, template)
        outpath = os.path.join(cwd, outpath)

    if only_update:
        if prev_subsd == subsd and \
           not missing_or_other_newer(outpath, template):
            return

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
    return outpath


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


def missing_or_other_newer(path, other_path, cwd=None):
    cwd = cwd or '.'
    path = get_abspath(path, cwd=cwd)
    other_path = get_abspath(other_path, cwd)
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
            raise IOError("No such file: {0}".format(fullpath))

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

def MetaReaderWriter(filename):
    class ReaderWriter(HasMetaData):
        metadata_filename = filename
    return ReaderWriter()


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


def download_files(websrc, files, md5sums, cwd=None,
                   only_if_missing=True, logger=None):
    for f in files:
        fpath = os.path.join(cwd, f) if cwd else f
        if not os.path.exists(fpath):
            import urllib2
            msg = 'Downloading: {0}'.format(websrc+f)
            if logger:
                logger.info(msg)
            else:
                print(msg)
            open(fpath, 'wt').write(urllib2.urlopen(websrc+f).read())
        fmd5 = md5_of_file(fpath).hexdigest()
        if fmd5 != md5sums[f]:
            raise ValueError(
                ("Warning: MD5 sum of {0} differs from that provided"+\
                 " in setup.py. i.e. {1} vs. {2}").format(
                     f, fmd5, md5sums[f]))
