#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sympy

from pycompilation import Cython_Code

def get_idxs(exprs):
    """
    Finds sympy.tensor.indexed.Idx instances and returns them.
    """
    idxs = set()
    def add_if_Idx(candidate):
        if isinstance(candidate, sympy.Idx):
            idxs.add(candidate)
    for expr in (exprs):
        assert len(expr.lhs) == 1
        add_if_Idx(expr.lhs)
        for atom in expr.rhs.atoms():
            add_if_Idx(atom)
    return idxs


def mk_recursive_loop(idxs, body):
    if len(idxs) > 0:
        return body
    else:
        idx = idxs[0]
        return Loop(idx.name,
                    self._idxs.index(idx), # sorry
                    mk_recursive_loop(idxs[1:], body)
        )


class ExampleCode(C_Code):

    def __init__(self, exprs, *args, **kwargs):
        self._exprs = exprs
        self._idxs = get_idxs(exprs)
        self._exprs_idxs = [
            tuple(sorted([
                i for i in self._idxs if i in expr.atoms()
            ])) for expr in self._exprs]
        self._expr_by_idx = DefaultDict(list)
        for expr, idxs in zip(self._exprs, self._exprs_idxs):
            self._expr_by_idx[idxs].append(expr)
        super(ExampleCode, self).__init__(*args, **kwargs)

    @property
    def variables(self):
        expr_groups = []
        for idxs in sorted(self._expr_by_idx.keys, key=len):
            expr_code = # something
            expr_groups.append(mk_recursive_loop(idxs, expr_code))
        return {'expr_groups': expr_groups}


class ExampleCodeWrapper(Cython_Code):
    pass


def make_callback():
    i_bounds = sympy.symbols('i_lbound i_ubound', integer=True)
    j_bounds = sympy.symbols('j_lbound j_ubound', integer=True)
    i = sympy.Idx('i', i_bounds)
    j = sympy.Idx('j', j_bounds)

    a_size = sympy.Symbol('a_size', integer=True)
    a = sympy.IndexedBase('a', shape=(a_size,))

    exprs = [
        x[i]=(a[i]/3-1)**i+c,
        y[j]=(a[j]/3-1)/c,
        z = c**2+a[d]
    ]

    example_code = ExampleCode(exprs)

    return example_code.compile_and_import_binary().my_callback


def main(data):
    """
    Show capabilities of codeexport when it comes to loop construction:

    x[i] = a[i]**i+c
    y[j] = a[j]/c
    z    = c**2+a[d]

    let i = i_lbound:i_ubound
    let j = j_lbound:j_ubound

    where input variables are:
      int a_size, double a[a_size], double c, int d,
      int i_lbound, int i_ubound, int j_lbound, int j_ubound

    and output variables are:
      x[i], y[j], z
    """
    cb = make_callback()
    data = {'a': np.linspace(3.0, 11.0, 7)
            'c': 3.14
            'd': 2
            'i_lbound': 0,
            'i_ubound': 7,
            'j_lbound': 2,
            'j_ubound': 5
            }
    result = cb(**data)
    print(result)


if __name__ == '__main__':
    main({'a_size': 10,
          ''})
