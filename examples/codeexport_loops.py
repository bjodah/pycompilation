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
            idxs.union(add_if_Idx(atom))
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

    _templates = ['codeexport_loops_template.c']

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
            dummy_groups = (
                DummyGroup('argdummies', self._)
            )
            cse_defs_code, exprs_in_cse_code = self.get_cse_code(
                self._expr_by_idx[idxs], 'cse', dummy_groups)
            expr_groups.append(mk_recursive_loop(idxs, expr_code))
        return {'expr_groups': expr_groups}


class ExampleCodeWrapper(Cython_Code):
    pass


def make_callback():
    i_bs = sympy.symbols('i_lb i_ub', integer=True)
    j_bs = sympy.symbols('j_lb j_ub', integer=True)
    i = sympy.Idx('i', i_bs)
    j = sympy.Idx('j', j_bs)

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
    The purpose of of this demo is to show capabilities of
    codeexport when it comes to loop construction:

    x[i] = (a[i]/3-1)**i+c
    y[j] = (a[j]/3-1)/c
    z    = c**2+a[d]

    let i = i_lb:i_ub  # lower and upper bounds
    let j = j_lb:j_ub

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
            'i_lb': 0,
            'i_ub': 7,
            'j_lb': 2,
            'j_ub': 5
            }
    result = cb(**data)
    print(result)


if __name__ == '__main__':
    main({'a_size': 10,
          ''})
