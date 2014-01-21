# -*- coding: utf-8 -*-

import fnmatch
import os
import pickle
import shutil
from collections import namedtuple
from hashlib import md5


from ._helpers import FileNotFoundError

def expand_collection_in_dict(d, key, new_items, no_duplicates=True):
    if key in d:
        if isinstance(d[key], set):
            map(d[key].add, new_items)
        elif isinstance(d[key], list):
            if no_duplicates:
                new_items = filter(
                    lambda x: x not in d[key], new_items)
            map(d[key].append, new_items)
        else:
            d[key] = d[key] + new_items
    else:
        d[key] = new_items

Glob = namedtuple('Glob', 'pathname')
ArbitraryDepthGlob = namedtuple('ArbitraryDepthGlob', 'filename')

def glob_at_depth(filename_glob, cwd=None):
    if cwd == None: cwd = '.'
    globbed = []
    for root, dirs, filenames in os.walk(cwd):
        for fn in filenames:
            if fnmatch.fnmatch(fn, filename_glob):
                globbed.append(os.path.join(root, fn))
    print('globbed', globbed)
    return globbed

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
        if not os.path.isabs(cwd):
            cwd = os.path.abspath(cwd)
        return os.path.abspath(
            os.path.join(cwd, path)
        )

def make_dirs(path, logger=None):
    if path[-1] == '/':
        parent = os.path.dirname(path[:-1])
    else:
        parent = os.path.dirname(path)

    if len(parent) > 0:
        if not os.path.exists(parent):
            make_dirs(parent, logger=logger)

    if not os.path.exists(path):
        if logger: logger.info("Making dir: "+path)
        os.mkdir(path, 0o777)
    else:
        assert os.path.isdir(path)


def copy(src, dst, only_update=False, copystat=True, cwd=None,
         dest_is_dir=False, create_dest_dirs=False, logger=None):
    """
    Augmented shutil.copy with extra options and slightly
    modified behaviour

    Arguments:
    -`only_update`: only copy if source is newer
        than destination (returns None)

    returns absolute path of dst if copy was performed
    """
    # Handle virtual working directory
    if cwd:
        if not os.path.isabs(src):
            src = os.path.join(cwd, src)
        if not os.path.isabs(dst):
            dst = os.path.join(cwd, dst)

    # Make sure source file extists
    if not os.path.exists(src):
        # Source needs to exist
        msg = "Source: `{}` does not exist".format(src)
        print(msg) # distutils just spits out `error: None`
        raise FileNotFoundError(msg)

    # We accept both (re)naming destination file _or_
    # passing a (possible non-existant) destination directory
    if dest_is_dir:
        if not dst[-1] == '/': dst = dst+'/'
    else:
        if os.path.exists(dst) and os.path.isdir(dst):
            dest_is_dir = True

    if dest_is_dir:
        dest_dir = dst
        dest_fname = os.path.basename(src)
        dst = os.path.join(dest_dir, dest_fname)
    else:
        dest_dir = os.path.dirname(dst)
        dest_fname = os.path.basename(dst)

    if not os.path.exists(dest_dir):
        if create_dest_dirs:
            make_dirs(dest_dir, logger=logger)
        else:
            msg = "You must create directory first."
            print(msg) # distutils just spits out `error: None`
            raise FileNotFoundError(msg)

    if only_update:
        if not missing_or_other_newer(dst, src):
            return

    if logger: logger.debug("Copying {} to {}".format(src, dst))

    if os.path.islink(dst):
        if os.path.abspath(os.path.realpath(dst)) == \
           os.path.abspath(dst):
            pass # destination is a symlic pointing to src
    else:
        shutil.copy(src, dst)
        if copystat:
            shutil.copystat(src, dst)
    return dst


def render_mako_template_to(
        template, outpath, subsd, only_update=False, cwd=None,
        prev_subsd=None, create_dest_dirs=False, logger=None,
        pass_warn_string=True, **kwargs):
    """
    template: either string of path or file like obj.

    Beware of the only_update option, it pays no attention to
    an updated subsd.

    pass_warn_string: defult True
    if True or instance of basetring:
    an extra vairable named '_warning_in_the_generated_file_not_to_edit'
    is passed with a preset (True) or string (basestring) warning not to
    directly edit the generated file.
    """
    if cwd:
        template = os.path.join(cwd, template)
        outpath = os.path.join(cwd, outpath)
    outdir = os.path.dirname(outpath)

    if not os.path.exists(outdir):
        if create_dest_dirs:
            make_dirs(outdir, logger=logger)
        else:
            raise FileNotFoundError(
                "Dest. dir. non-existent: {}".format(outdir))

    if only_update:
        if prev_subsd == subsd and not \
           missing_or_other_newer(outpath, template):
            if logger:
                msg = "Did not re-render {}. (destination newer + same dict)"
                logger.info(msg.format(template))
            return

    msg = None
    if pass_warn_string == True:
        subsd['_warning_in_the_generated_file_not_to_edit'] = (
            "DO NOT EDIT THIS FILE! (Generated from template: {} using"+\
            " Mako python templating engine)").format(
                os.path.basename(template))
    elif isinstance(pass_warn_string, basestring):
        subsd['_warning_in_the_generated_file_not_to_edit'] =\
            pass_warn_string

    if hasattr(template, 'read'):
        # set in-file handle to provided template
        ifh = template
    else:
        # Assume template is a string of the path to the template
        ifh = open(template, 'rt')

    template_str = ifh.read()

    kwargs_Template = {'input_encoding': 'utf-8', 'output_encoding': 'utf-8'}
    kwargs_Template.update(kwargs)
    with open(outpath, 'wt') as ofh:
        from mako.template import Template
        from mako.exceptions import text_error_template
        try:
            rendered = Template(template_str, **kwargs_Template).render(**subsd)
        except:
            print(text_error_template().render())
            raise
        if logger: logger.info("Rendering '{}' to '{}'...".format(ifh.name, outpath))
        ofh.write(rendered)
    return outpath


def md5_of_file(path, nblocks=128):
    """
    Use .digest() or .hexdigest() on returned object
    to get binary or hex encoded string.
    """
    md = md5()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(nblocks*md.block_size), b''):
             md.update(chunk)
    return md


def missing_or_other_newer(path, other_path, cwd=None):
    cwd = cwd or '.'
    path = get_abspath(path, cwd=cwd)
    other_path = get_abspath(other_path, cwd=cwd)
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
            raise FileNotFoundError(
                "No such file: {0}".format(fullpath))

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


def import_(filename, only_if_newer_than=None):
    """
    Imports (cython generated) shared object file (.so)

    Provide a list of paths in `only_if_newer_than` to check
    timestamps of dependencies. import_ raises an ImportError
    if any is newer.

    Word of warning: Python's caching or the OS caching (unclear to author)
    is horrible for reimporting same path of an .so file. It will
    not detect the new time stamp nor new checksum but will use old
    module.

    Use unique names for this reason
    """
    import imp
    path, name = os.path.split(filename)
    name, ext = os.path.splitext(name)
    fobj, filename, data = imp.find_module(name, [path])
    if only_if_newer_than:
        for dep in only_if_newer_than:
            if os.path.getmtime(filename) < os.path.getmtime(dep):
                raise ImportError("{} is newer than {}".format(dep, filename))
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

# def callback_on_regexp_path(path, regexp_tuples, default):
#     dirname = os.path.dirname(path)
#     filename = os.path.basename(path)
#     for pattern, target, cb, args, kwargs in regexp_tuples:
#         if re.match(pattern, filename):
#             tgt = os.path.join(dirname, re.sub(
#                     pattern, target, filename))
#             cb(get_abspath(path),
#                *args,
#                **kwargs,
#                os.path.join(self.build_temp, tgt),
#                subsd,
#                only_update=True,
#                create_dest_dirs=True)
#             sources.append(tgt)
#             print(tgt)
#             break
#     else:
#         copy(f,
#              os.path.join(self.build_temp,
#                           os.path.dirname(f)),
#              dest_is_dir=True,
#              create_dest_dirs=True)
#         sources.append(f)
