import os

from collections import namedtuple
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from distutils.spawn import find_executable

def uniquify(l):
    result = []
    for x in l:
        if not x in result:
            result.append(x)
    return result

def expand_collection_in_dict(d, key, new_items):
    if key in d:
        if isinstance(d[key], set):
            map(d[key].add, new_items)
        elif isinstance(d[key], list):
            map(d[key].append, new_items)
        else:
            d[key] = d[key] + new_items
    else:
        d[key] = new_items


def find_binary_of_command(candidates):
    """
    Currently only support *nix systems (invocation of which)
    """
    for c in candidates:
        binary_path = find_executable(c)
        if c and binary_path:
            return c, binary_path
    raise RuntimeError('No binary located for candidates: {}'.format(
        candidates))


def defaultnamedtuple(name, args, defaults=None):
    """
    defaultnamedtuple returns a new subclass of Tuple with named fields
    and a constructor with implicit default values.

    >>> Body = namedtuple('Body', 'x y z density', (1.0,))
    >>> Body.__doc__
    SOMETHING
    >>> b = Body(10, z=3, y=5)
    >>> b._asdict()
    {'densidty': 1.0, 'x': 10, 'y': 5, 'z': 3}
    """
    if defaults == None: defaults = ()
    nt = namedtuple(name, args)
    kw_order = args.split() if isinstance(args, basestring) else args
    nargs = len(kw_order)

    def factory(*args, **kwargs):
        n_missing = nargs-len(args)
        if n_missing > 0:
            unset = OrderedDict(zip(kw_order[-n_missing:],
                                    defaults[-n_missing:]))
            unset.update(kwargs)
            return nt(*(args+tuple(unset.values())))
        else:
            return nt(*args)
    factory.__doc__ = nt.__doc__
    return factory


def assure_dir(path):
    if os.path.exists(path):
        assert os.path.isdir(path)
    else:
        os.mkdir(path)
