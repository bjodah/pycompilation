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

    templates = ['codeexport_loops_template.c']
    copy_files = ['codeexport_loops_wrapper.o']


    def __init__(self, exprs, inputs, indices, **kwargs):
        self.exprs = exprs
        self.inputs = inputs
        self.indices = indices
        assert get_idxs(exprs) == sorted(indices) # sanity check

        # list of lists ox indices present in each expr
        self._exprs_idxs = [tuple(
            [i for i in self.indices if i in expr.lhs.atoms()]) \
            for expr in self.exprs]

        # Group expressions using same set of indices
        self._expr_by_idx = DefaultDict(list)
        for idxs, expr in zip(self._exprs_idxs, self._exprs):
            self._expr_by_idx[idxs].append(expr)
        super(ExampleCode, self).__init__(**kwargs)


    @property
    def variables(self):
        expr_groups = []
        for idxs in self._exprs_idxs:
            # dummy_groups = (
            #     DummyGroup('argdummies', self._)
            # )
            code = self.as_arrayified_code(self._expr_by_idx[idxs])
            expr_groups.append(mk_recursive_loop(idxs, expr_code))
        return {'expr_groups': expr_groups}


def model1(a_arr, c_, ilim, jlim):
    """
    x[i] = (a[i]/3-1)**i + c
    """
    i_bs = sympy.symbols('i_lb i_ub', integer=True)
    i = sympy.Idx('i', i_bs)

    j_bs = sympy.symbols('j_lb j_ub', integer=True)
    j = sympy.Idx('j', j_bs)


    # a_size >= i_ub - i_lb
    a_size = sympy.Symbol('a_size', integer=True)
    a = sympy.IndexedBase('a', shape=(a_size,))

    c = sympy.Symbol('c', real=True)

    x = sympy.IndexedBase('x', shape=(a_size,))


    exprs = [
        Eq(x[i], (a[i]/3-1)**i+c),
        Eq(y[j], a[j]-j),
    ]

    ex_code = ExampleCode(exprs, (a[i],c), (i, j))
    mod = ex_code.compile_and_import_binary()


    x_, y_ = mod.my_callback(a_arr, c_, bounds=(i_bounds, j_bounds))
    assert np.allclose(x_, (a_arr/3-1)**np.arange(ilim[0], ilim[1]+1) - c_)
    assert np.allclose(y_, a_arr-np.arange(jlim[0],jlim[1]+1))


def model2():
    """
    y[j] = Sum(a[i], i, j-2, j+2)
    """
    pass

def main():
    a_arr = np.linspace(0,10,11)
    c_ = 3.5
    model1(a_arr, c_, (3,7), (2,6))


if __name__ == '__main__':
    main()
