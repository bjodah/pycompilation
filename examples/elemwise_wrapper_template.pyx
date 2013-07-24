import numpy as np
cimport numpy as cnp

%for (opname, opsymb), (ctype, nptype) in combos:
cdef extern void c_elem${opname}_${ctype}(const ${idxtype} N,
                                     const ${ctype}* a,
                                     const ${ctype}* b,
                                     ${ctype}* z)
%endfor

%for opname, opsymb in ops:
def elem${opname}(a, b):
    if not isinstance(a, np.ndarray):
        raise TypeError('Numpy arrays only supported.')
    %for ctype, nptype in types:
    elif a.dtype == np.${nptype}:
        return _elem${opname}_${ctype}(a,b)
    %endfor
    raise RuntimeError('Unsupported dtype')

%endfor

%for (opname, opsymb), (ctype, nptype) in combos:
cdef _elem${opname}_${ctype}(${ctype} [:] a,
                               ${ctype} [:] b):
    cdef cnp.ndarray[cnp.${nptype}_t, ndim=1] c = np.empty_like(
        a, dtype=np.${nptype})
    c_elem${opname}_${ctype}(a.shape[0],
                             &a[0],
                             &b[0],
                             &c[0])
    return c

%endfor
