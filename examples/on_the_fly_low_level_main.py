#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This example clearly motivates the existance of Cython...

Code based on:
https://docs.python.org/3/howto/cporting.html

Note that the code is most likely quite fragile..

Make sure you have (on debian based systems):
python-dev  and/or  python3-dev
"""

from __future__ import print_function, division, absolute_import


from pycompilation import compile_link_import_strings


sources_ = [('adder.c', r"""
#include "Python.h"

double double_binary_add(double a, double b){
    return a+b;
}


PyDoc_STRVAR(adder__doc__,
"Module for adding stuff.");

PyDoc_STRVAR(add__doc__,
"Adds two doubles.");

static PyObject *
py_binary_add(PyObject *self, PyObject *args){
    double x=0, y=0;
    if (!PyArg_ParseTuple(args, "dd", &x, &y))
        return NULL;
    return PyFloat_FromDouble(double_binary_add(x, y));
}

static PyMethodDef adder_methods[] = {
    {"add", (PyCFunction)py_binary_add, METH_VARARGS, add__doc__},
    {NULL, NULL}
};

#if PY_MAJOR_VERSION >= 3

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "adder",
    NULL,
    NULL,
    adder_methods,
    NULL,
    NULL,
    NULL,
    NULL
};

#define INITERROR return NULL
PyObject *
PyInit_adder(void)

#else
#define INITERROR return
void initadder(void)

#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule3("adder", adder_methods, adder__doc__);
#endif

    if (module == NULL)
        INITERROR;
#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}
""")]


def main():
    from distutils.sysconfig import get_python_inc
    mod = compile_link_import_strings(
        sources_, include_dirs=[get_python_inc()], std="c99")
    assert abs(mod.add(2.0, 4.0) - 6.0) < 1e-15
    assert abs(mod.add(2, 2) - 4.0) < 1e-15
    try:
        mod.add('a', 'b')
    except TypeError:
        pass
    else:
        raise RuntimeError("Something's not quite right...")
    print("All went well!")


if __name__ == '__main__':
    main()
