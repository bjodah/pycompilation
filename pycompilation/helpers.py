from collections import OrderedDict, namedtuple


def defaultnamedtuple(name, args, defaults):
    nt = namedtuple(name, args)
    kw_order = args.split()
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
