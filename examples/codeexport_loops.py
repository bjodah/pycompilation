#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sympy

from pycompilation.codeexport import C_Code

def get_statements(eq, taken=None):
    """
    Returns a list of Eq objects were lhs is variable to make
    assignment to and rhs is expr to be evaluated.

    Unwinds Sum() and Product() objects into loops
    """
    stmnts = []
    # maybe make taken to be a set
    taken = set()
    for x in eq.atoms:
        if x.is_Symbol: taken.add(x)

    #taken = taken or []
    #taken += [x for x in eq.atoms() if x.is_Symbol and x not in taken]

    i = 0
    def new_symb():
        base = '_symb_tmp__'
        i += 1
        candidate = sympy.Symbol(base+str(i))
        if not candidate in taken:
            taken.add(candidate)
            return candidate
        else:
            i += 1
            return new_symb()

    def argify(a):
        if arg.is_Symbol:
            return a
        else:
            if isinstance(a, sympy.Sum):
                s = new_symb()
                expr, loopv = a.args[0], a.args[1]
                sub_stmnts(get_statements(expr), taken)
                stmnts.append(Loop(sub_stmnts, loopv))
            elif isinstance(a, sympy.Product):
                raise NotImplementedError
            else:
                raise NotImplementedError

    stmnts.extend(type(stmnts)([argify(arg) for arg in stmts.args]))
    return stmnts


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
    return sorted(idxs)


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
                i for i in self._idxs if i in expr.lhs.atoms()
            ])) for expr in self._exprs]
        self._expr_by_idx = DefaultDict(list)
        for idxs, expr in zip(self._exprs_idxs, self._exprs):
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




def make_callback():
    """
    For performance: Choose least strided index to have highest alphabetic order
    """
    i_bs = sympy.symbols('i_lb i_ub', integer=True)
    j_bs = sympy.symbols('j_lb j_ub', integer=True)
    i = sympy.Idx('i', i_bs)
    j = sympy.Idx('j', j_bs)

    a_size = sympy.Symbol('a_size', integer=True)
    a = sympy.IndexedBase('a', shape=(a_size,))

    exprs = [
        Eq(x[i],(a[i]/3-1)**i+c),
        Eq(y[j],(sympy.Sum(a[i], i, j-2, j+2)/3-1)/c),
        Eq(z, c**2+a[d])
    ]

    example_code = ExampleCode(exprs)

    return example_code.compile_and_import_binary().my_callback


def main():
    """
    The purpose of of this demo is to show capabilities of
    codeexport when it comes to loop construction:

    x[i] = (a[i]/3-1)**i+c
    y[j] = (Sum(a[i], i, j-2, j+2)/3-1)/c
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
            'c': 3.14,
            'd': 2,
            'bounds': {'i': (0,7),
                       'j': (2,5)}
            }
    result = cb(**data)
    print(result)


if __name__ == '__main__':
    main()
