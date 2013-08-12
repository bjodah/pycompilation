import numpy as np
cimport numpy as cnp

cdef extern void do_mtxmul(int * m, int * n, int * o, double * A, double * B, double * Out)

def mtxmul(A, B):
    cdef cnp.ndarray[cnp.float64_t, ndim=2, mode='fortran'] A_fort =\
        np.asfortranarray(A)
    cdef cnp.ndarray[cnp.float64_t, ndim=2, mode='fortran'] B_fort =\
        np.asfortranarray(B)
    cdef int m = A.shape[0]
    cdef int n = A.shape[1]
    cdef int o = B.shape[1]
    cdef cnp.ndarray[cnp.float64_t, ndim=2, mode='fortran'] Out = np.empty((m, o), order='F')

    assert A.shape[1] == B.shape[0]

    do_mtxmul(&m, &n, &o,
          &A_fort[0,0], #.data,
          &B_fort[0,0], #<double*>
          &Out[0,0])

    return Out
