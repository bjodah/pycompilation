// mako template of C99 source
// Lightning fast newton iteration for finding inverse of a function
// variables:
// y_lo, y_hi, x_lo, x_hi, lookup_N, lookup_x, lookup_poly, poly_expr, order, cses, y_in_cse, dydx_in_cse

#include <math.h>
#include "invnewton.h"

static inline double dabs(const double x){return x > 0 ? x : -x;}

const double y_lo = ${ylim[0]};
const double y_hi = ${ylim[1]};
const double y_span = ${ylim[1]} - ${ylim[0]};
const double y_space = (${ylim[1]} - ${ylim[0]})/(${lookup_N}-1.0);

const double x_lo = ${xlim[0]};
const double x_hi = ${xlim[1]};
const double x_span = ${xlim[1]} - ${xlim[0]};

const int ndpp = ${order+1}; // number of data per point
const int lookup_N = ${lookup_N};
// lookup_x is [x(y0), dxdy(y0), d2xdy2(y0), ..., 
//     dZdxdyZ(y0), ..., x(yN), dxdy(yN), d2xdy2(yN), ..., dZxdyZ(yN)]
// where Z is (order+1)/2, where order is the order of the polynomial
const double lookup_x[${lookup_N*(order+1)}] = {${			\
    ', '.join(map('{0:.17e}'.format, lookup_x))}}; // for equidistant y [y_lo ... y_hi], 

static double approx_x(double y){
  // Polynomial interpolation between lookup points
  int idx = ${lookup_N-1}*((y${"{0:+23.17e}".format(-ylim[0])})/y_span);
  int tbl_offset = ndpp*idx;
  double localy = y-y_space*idx;
  return ${poly_expr}; // lookup_x[tbl_offset+i]
}

int c_invnewton(double y, double * restrict xout, double abstol_y, 
		double abstol_x, int iabstol, int itermax, int save_conv, double * restrict conv_dx)
{
  // iabstol: 0 => abstol_y, 1 => abstol_x, 2 => abstol_y & abstol_x
  // if save_conv == 1; ensure sizeof(conv_dx) >= sizeof(double)*itermax
  // returns -1 if itermax reached, elsewise number of iterations
  double x = approx_x(y);
  int i=0;
  %for token, expr in cses:
  double ${token} = ${expr};
  %endfor
  double dy = ${y_in_cse}-y;
  double dx = -dy/(${dydx_in_cse});

  for(;;){ // infite loop
    x += dx;
    %for token, expr in cses:
    ${token} = ${expr};
    %endfor
    dy = ${y_in_cse}-y;
    if(save_conv)
      conv_dx[i] = dx;
    switch(iabstol){
    case (0):
      if (dabs(dy) < abstol_y) goto exit_loop;
      break;
    case (1):
      if (dabs(dx) < abstol_x) goto exit_loop;
      break;
    case (2):
      if ((dabs(dy) < abstol_y) && (dabs(dx) < abstol_x)) goto exit_loop;
      break;
    }
    i++;
    if (i >= itermax) return -1;
    dx = -dy/(${dydx_in_cse});
  }
 exit_loop: // double break not possible
  *xout = x;
  return i+1;
}

int c_invnewton_arr(int ny, const double * restrict y, double * restrict x, 
		    double abstol_y, double abstol_x, int iabstol, int itermax)
{
  // Returns -1 on successful exit
  // Returns index of a failing c_invnewton call (OpenMP)
  int status = -1;
  #pragma omp parallel for
  for (int i=0; i<ny; ++i){
    int success = c_invnewton(y[i], &x[i], abstol_y, abstol_x, iabstol, itermax, 0, NULL);
    if(success == -1)
      status = i;
  }
  return status;
}





