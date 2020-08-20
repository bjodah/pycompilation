# -*- coding: utf-8 -*-

from __future__ import print_function, division, absolute_import

import fnmatch
import os
import pickle
import shutil

from collections import namedtuple
from hashlib import md5


class CompilationError(Exception):
    pass


class FileNotFoundError(Exception):
    pass


def expand_collection_in_dict(d, key, new_items, no_duplicates=True):
    """
    Parameters
    d: dict
        dict in which a key will be inserted/expanded
    key: hashable
        key in d
    new_items: iterable
        d[key] will be extended with items in new_items
    no_duplicates: bool
        avoid inserting duplicates in d[key] (default: True)
    """
    if key in d:
        if no_duplicates:
            new_items = filter(lambda x: x not in d[key], new_items)
        if isinstance(d[key], set):
            map(d[key].add, new_items)
        elif isinstance(d[key], list):
            map(d[key].append, new_items)
        else:
            d[key] = d[key] + new_items
    else:
        d[key] = new_items


Glob = namedtuple('Glob', 'pathname')
ArbitraryDepthGlob = namedtuple('ArbitraryDepthGlob', 'filename')


def glob_at_depth(filename_glob, cwd=None):
    if cwd is not None:
        cwd = '.'
    globbed = []
    for root, dirs, filenames in os.walk(cwd):
        for fn in filenames:
            if fnmatch.fnmatch(fn, filename_glob):
                globbed.append(os.path.join(root, fn))
    return globbed


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
        if logger:
            logger.info("Making dir: "+path)
        os.mkdir(path, 0o777)
    else:
        assert os.path.isdir(path)


def copy(src, dst, only_update=False, copystat=True, cwd=None,
         dest_is_dir=False, create_dest_dirs=False, logger=None):
    """
    Augmented shutil.copy with extra options and slightly
    modified behaviour

    Parameters
    ==========
    src: string
        path to source file
    dst: string
        path to destingation
    only_update: bool
        only copy if source is newer than destination
        (returns None if it was newer), default: False
    copystat: bool
        See shutil.copystat. default: True
    cwd: string
        Path to working directory (root of relative paths)
    dest_is_dir: bool
        ensures that dst is treated as a directory. default: False
    create_dest_dirs: bool
        creates directories if needed.
    logger: logging.Looger
        debug level info emitted. Passed onto make_dirs.

    Returns
    =======
    Path to the copied file.

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
        raise FileNotFoundError(msg)

    # We accept both (re)naming destination file _or_
    # passing a (possible non-existant) destination directory
    if dest_is_dir:
        if not dst[-1] == '/':
            dst = dst+'/'
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
            raise FileNotFoundError(msg)

    if only_update:
        if not missing_or_other_newer(dst, src):
            if logger:
                logger.debug(
                    "Did not copy {} to {} (source not newer)".format(
                        src, dst))
            return

    if os.path.islink(dst):
        if os.path.abspath(os.path.realpath(dst)) == \
           os.path.abspath(dst):
            pass  # destination is a symlic pointing to src
    else:
        if logger:
            logger.debug("Copying {} to {}".format(src, dst))
        shutil.copy(src, dst)
        if copystat:
            shutil.copystat(src, dst)
    return dst


def md5_of_file(path, nblocks=128):
    """
    Computes the md5 hash of a file.

    Parameters
    ==========
    path: string
        path to file to compute hash of

    Returns
    =======
    hashlib md5 hash object. Use .digest() or .hexdigest()
    on returned object to get binary or hex encoded string.
    """
    md = md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(nblocks*md.block_size), b''):
            md.update(chunk)
    return md


def md5_of_string(string):
    md = md5()
    md.update(string)
    return md


def missing_or_other_newer(path, other_path, cwd=None):
    """
    Investigate if path is non-existant or older than provided reference
    path.

    Parameters
    ==========
    path: string
        path to path which might be missing or too old
    other_path: string
        reference path
    cwd: string
        working directory (root of relative paths)

    Returns
    =======
    True if path is older or missing.
    """
    cwd = cwd or '.'
    path = get_abspath(path, cwd=cwd)
    other_path = get_abspath(other_path, cwd=cwd)
    if not os.path.exists(path):
        return True
    if os.path.getmtime(other_path) - 1e-6 >= os.path.getmtime(path):
        # 1e-6 is needed beacuse http://stackoverflow.com/questions/17086426/
        return True
    return False


class HasMetaData(object):
    """
    Provides convenice classmethods for a class to pickle some metadata.
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
            d = pickle.load(open(fullpath, 'rb'))
            return d[key]
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
            d = pickle.load(open(fullpath, 'rb'))
            d.update({key: value})
            with open(fullpath, 'wb') as ofh:
                pickle.dump(d, ofh)
        else:
            with open(fullpath, 'wb') as ofh:
                pickle.dump({key: value}, ofh)


def MetaReaderWriter(filename):
    class ReaderWriter(HasMetaData):
        metadata_filename = filename
    return ReaderWriter()


def import_module_from_file(filename, only_if_newer_than=None):
    """
    Imports (cython generated) shared object file (.so)

    Provide a list of paths in `only_if_newer_than` to check
    timestamps of dependencies. import_ raises an ImportError
    if any is newer.

    Word of warning: Python's caching or the OS caching (unclear to author)
    is horrible for reimporting same path of an .so file. It will
    not detect the new time stamp nor new checksum but will use old
    module.

    Use unique names for this reason.

    Parameters
    ==========
    filename: string
        path to shared object
    only_if_newer_than: iterable of strings
        paths to dependencies of the shared object

    Raises
    ======
    ImportError if any of the files specified in only_if_newer_than are newer
    than the file given by filename.
    """
    import imp
    path, name = os.path.split(filename)
    name, ext = os.path.splitext(name)
    name = name.split('.')[0]
    fobj, filename, data = imp.find_module(name, [path])
    if only_if_newer_than:
        for dep in only_if_newer_than:
            if os.path.getmtime(filename) < os.path.getmtime(dep):
                raise ImportError("{} is newer than {}".format(dep, filename))
    mod = imp.load_module(name, fobj, filename, data)
    return mod


def find_binary_of_command(candidates):
    """
    Calls `find_executable` from distuils for
    provided candidates and returns first hit.
    If no candidate mathces, a RuntimeError is raised
    """
    from distutils.spawn import find_executable
    for c in candidates:
        binary_path = find_executable(c)
        if c and binary_path:
            return c, binary_path
    raise RuntimeError('No binary located for candidates: {}'.format(
        candidates))


def pyx_is_cplus(path):
    """
    Inspect a Cython source file (.pyx) and look for comment line like:

    # distutils: language = c++

    Returns True if such a file is present in the file, else False.
    """
    for line in open(path, 'rt'):
        if line.startswith('#') and '=' in line:
            splitted = line.split('=')
            if len(splitted) != 2:
                continue
            lhs, rhs = splitted
            if lhs.strip().split()[-1].lower() == 'language' and \
               rhs.strip().split()[0].lower() == 'c++':
                    return True
    return False


def uniquify(l):
    """
    Uniquify a list (skip duplicate items).
    """
    result = []
    for x in l:
        if x not in result:
            result.append(x)
    return result
