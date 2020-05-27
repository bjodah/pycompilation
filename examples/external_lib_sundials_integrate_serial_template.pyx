from libc.stdlib cimport malloc, free
cimport numpy as cnp
import numpy as np

cdef extern from *:
    int integrate(double *, double *, int,
                  int, void*, double*,
                  double, double*, long int *)

def solve_ivp(cnp.ndarray[cnp.float64_t, ndim=1] tout,
              cnp.ndarray[cnp.float64_t, ndim=1] y0,
              cnp.ndarray[cnp.float64_t, ndim=1] params,
              cnp.ndarray[cnp.float64_t, ndim=1] abstol,
              double reltol):
    cdef:
        int status = 0
        int nt = tout.size
        int ny = y0.size
        long int * info = <long int *>malloc(8*sizeof(long int))
        cnp.ndarray[cnp.float64_t, ndim=2] yout = np.empty((nt, ny))
    if abstol.size == 1:
        abstol = np.tile(abstol, y0.size)
    assert abstol.size == y0.size, 'abstol size mismatch'
    status = integrate(&tout[0], &y0[0], nt, ny, <void *>(params.data), &abstol[0], reltol, &yout[0, 0], info)
    nfo = {
        'num_steps': info[0],
        'num_rhs': info[1],
        'num_lin_solv_setups': info[2],
        'num_err_test_fails': info[3],
        'num_nonlin_solv_iters': info[4],
        'num_nonlin_solv_conv_fails': info[5],
        'num_dls_jac_evals': info[6],
        'num_dls_rhs_evals': info[7],
        'status': status
    }
    free(info)
    return yout, nfo
