import numpy as np
cimport numpy as cnp

cdef extern int c_invnewton(double y, double * x, double abstol,
    int itermax, int save_conv, double * conv_dx)
cdef extern int c_invnewton_arr(
    int ny, double * y, double * x, double abstol, int itermax)

def invnewton(y, double abstol=1e-12, int itermax=16):
    cdef int i
    cdef double x
    cdef cnp.ndarray[cnp.float64_t, ndim=1] xarr, yarr
    cdef int ny, status
    if isinstance(y, np.ndarray):
        yarr = y
    else:
        yarr = np.array([y])
    ny = yarr.size
    xarr = np.empty(ny, dtype=np.float64)
    if ny == 1:
        status = c_invnewton(yarr[0], &x, abstol, itermax, 0, NULL)
        if status == 1:
            raise RuntimeError(("Maximum number of iterations"+\
                               " reached ({})").format(itermax))
        return x
    else:
        status = c_invnewton_arr(ny, &yarr[0], &xarr[0], abstol, itermax)
        if status != -1:
            raise RuntimeError(
                ("Maximum number of iterations reached ({}) for"+\
                " (at least) index {}").format(itermax, status))
        return xarr
