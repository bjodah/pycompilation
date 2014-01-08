#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import defaultdict

import numpy as np
import sympy

from pycompilation.codeexport import C_Code, Loop

def get_statements(eq, taken=None):
    """
    Returns a list of Eq objects were lhs is variable to make
    assignment to and rhs is expr to be evaluated.

    Transforms Sum() and Product() objects into Loop instances
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
    for expr in (exprs):
        for i in expr.find(sympy.Idx):
            idxs.add(i)
    return sorted(idxs, cmp=lambda x,y: str(x)<str(y))



class ExampleCode(C_Code):

    templates = ['codeexport_loops_template.c']
    source_files = ['codeexport_loops_wrapper.pyx']


    def __init__(self, eqs, inputs, indices, **kwargs):
        self.unk = [x.lhs for x in eqs]
        self.exprs = [x.rhs for x in eqs]
        self.inputs = inputs
        self.indices = indices
        assert get_idxs(exprs) == sorted(
            indices, cmp=lambda x,y: str(x)<str(y)) # sanity check

        # list of lists of indices present in each expr
        self._exprs_idxs = [tuple(
            [i for i in self.indices if expr.lhs.find(i)]) \
            for expr in self.exprs]

        # Group expressions using same set of indices
        self._expr_by_idx = defaultdict(list)
        for idxs, expr in zip(self._exprs_idxs, self.exprs):
            self._expr_by_idx[idxs].append(expr)

        super(ExampleCode, self).__init__(**kwargs)

    def _mk_recursive_loop(self, idxs, body):
        if len(idxs) == 0:
            return body
        else:
            idx = idxs[0]
            return Loop(
                idx.name,
                self.indices.index(idx), # sorry
                mk_recursive_loop(idxs[1:], body)
            )

    @property
    def variables(self):
        expr_groups = []
        for idxs in self._exprs_idxs:
            # dummy_groups = (
            #     DummyGroup('argdummies', self._)
            # )
            expr_code = []
            for expr in self._expr_by_idx[idxs]:
                expr_code.append(self.as_arrayified_code(expr))
            expr_groups.append(self._mk_recursive_loop(
                idxs, expr_code.join('\n')))
        return {'expr_groups': expr_groups}

    _mod = None
    @property
    def mod(self):
        if self._mod == None:
            self._mod = self.compile_and_import_binary()
        return self._mod

    def __call__(self, inp, bounds=None, inpi=None):
        inpd = np.ascontiguousarray(np.concatenate([[x] if isinstance(x, float) else x for x in inp))
        noutd =
        x_, y_ = self.mod.arbitrary_func(bounds, inpd, inpi, noutd, nouti)

def model1(inps, lims):
    """
    x[i] = (a[i]/3-1)**i + c
    y[j] = a[j] - j
    """
    a_arr, c_ = inps
    ilim, jlim = lims
    i_bs = sympy.symbols('i_lb i_ub', integer=True)
    i = sympy.Idx('i', i_bs)

    j_bs = sympy.symbols('j_lb j_ub', integer=True)
    j = sympy.Idx('j', j_bs)


    # a_size >= i_ub - i_lb
    a_size = sympy.Symbol('a_size', integer=True)
    a = sympy.IndexedBase('a', shape=(a_size,))

    c = sympy.Symbol('c', real=True)

    x = sympy.IndexedBase('x', shape=(a_size,))
    y = sympy.IndexedBase('y', shape=(a_size,))

    eqs = [
        sympy.Eq(x[i], (a[i]/3-1)**i+c),
        sympy.Eq(y[j], a[j]-j),
    ]

    ex_code = ExampleCode(eqs, (a[i], c), (i, j))
    x_, y_ = ex_code(inps, bounds=(i_bounds, j_bounds))
    assert np.allclose(
        x_, (a_arr/3-1)**np.arange(ilim[0], ilim[1]+1) - c_)
    assert np.allclose(
        y_, a_arr-np.arange(jlim[0],jlim[1]+1))


def model2():
    """
    y[j] = Sum(a[i], i, j-2, j+2)
    """
    pass

def main():
    a_arr = np.linspace(0,10,11)
    c_ = 3.5
    model1([a_arr, c_], [(3,7), (2,6)])


if __name__ == '__main__':
    main()
