import os

from collections import namedtuple
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from distutils.spawn import find_executable


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


def uniquify(l):
    result = []
    for x in l:
        if not x in result:
            result.append(x)
    return result


def expand_collection_in_dict(d, key, new_items, no_duplicates=True):
    if key in d:
        if isinstance(d[key], set):
            map(d[key].add, new_items)
        elif isinstance(d[key], list):
            if no_duplicates:
                new_items = filter(lambda x: x not in d[key], new_items)
            map(d[key].append, new_items)
        else:
            d[key] = d[key] + new_items
    else:
        d[key] = new_items


def find_binary_of_command(candidates):
    """
    Calls `find_executable` from distuils for
    provided candidates and returns first hit.
    If no candidate mathces, a RuntimeError is raised
    """
    for c in candidates:
        binary_path = find_executable(c)
        if c and binary_path:
            return c, binary_path
    raise RuntimeError('No binary located for candidates: {}'.format(
        candidates))


def defaultnamedtuple(name, args, defaults=(), typing=()):
    """
    defaultnamedtuple returns a new subclass of Tuple with named fields
    and a constructor with implicit default values.

    Arguments:
    -`name`: the name of the class
    -`args`: a tuple or a splitable string
    -`defaults`: default values for args, counting [-len(defaults):]
    -`typing`: optional requirements for type, counting [:len(typing)]
               should be an iterable of callbacks returning True for
               conformance.

    Example

    >>> Body = namedtuple('Body', 'x y z density', (1.0,))
    >>> Body.__doc__
    SOMETHING
    >>> b = Body(10, z=3, y=5)
    >>> b._asdict()
    {'density': 1.0, 'x': 10, 'y': 5, 'z': 3}
    """
    nt = namedtuple(name, args)
    kw_order = args.split() if isinstance(args, basestring) else args
    nargs = len(kw_order)

    # Sanity check that `defaults` conform to typing
    if len(typing) + len(defaults) > nargs:
        # there is an overlap
        noverlap = len(typing) + len(defaults) - nargs
        for i, t in enumerate(typing[-noverlap:]):
            assert t(defaults[i])

    # We will be returning a factory which intercepts before
    # calling our namedtuple constructor
    def factory(*args, **kwargs):
        # Set defaults for missing args
        n_missing = nargs-len(args)
        if n_missing > 0:
            unset = OrderedDict(zip(kw_order[-n_missing:],
                                    defaults[-n_missing:]))
            unset.update(kwargs)
            args += tuple(unset.values())

        # Type checking
        for i, t in enumerate(typing):
            if not t(args[i]):
                raise ValueError('Argument {} ({}) does not conform to'+\
                                 ' typing requirements'.format(i, args[i]))
        # Construct namedtuple instance and return it
        return nt(*args)
    factory.__doc__ = nt.__doc__
    return factory


def assure_dir(path):
    """
    Asserts that path is direcory, if it does
    not exist: it is created.
    """
    if os.path.exists(path):
        assert os.path.isdir(path)
    else:
        os.mkdir(path)


def line_cont_after_delim(ctx, s, line_len=40, delim=(',',),
                          line_cont_token='&'):
    """
    Insert newline (with preceeding `line_cont_token`) afer
    passing over a delimiter after traversing at least `line_len`
    number of characters

    Mako convenience function. E.g. fortran does not
    accpet lines of arbitrary length.
    """
    last = -1
    s = str(s)
    for i,t in enumerate(s):
        if t in delim:
            if i > line_len:
                if last == -1:
                    raise ValueError('No delimiter until already past line_len')
                i = last
                return s[:i+1] + line_cont_token + '\n ' + line_cont_after_delim(
                    ctx, s[i+1:], line_len, delim)
            last = i
    return s
