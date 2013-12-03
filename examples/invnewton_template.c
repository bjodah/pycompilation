// mako template of C99 source
// Lightning fast newton iteration for finding inverse of a function
// variables:
// y_lo, y_hi, x_lo, x_hi, lookup_N, lookup_x, lookup_poly, poly_expr, order, cses, y_in_cse, dydx_in_cse

#include <math.h>

#define NULL 0
static inline double abs(const double x){return x ? x > 0 : -x;}

const double y_lo = ${ylim[0]};
const double y_hi = ${ylim[1]};
const double y_span = ${ylim[1]} - ${ylim[0]};
const double y_space = (${ylim[1]} - ${ylim[0]})/(${lookup_N}-1.0);

const double x_lo = ${xlim[0]};
const double x_hi = ${xlim[1]};
const double x_span = ${xlim[1]} - ${xlim[0]};

const int ndpp = ${order+1}; // number of data per point, e.g. (x, dxdy, d2xdy2) => ndpp == 3
const int lookup_N = ${lookup_N};
// lookup_x is [x(y0), dxdy(y0), d2xdy2(y0), ..., 
//     dZdxdyZ(y0), ..., x(yN), dxdy(yN), d2xdy2(yN), ..., dZxdyZ(yN)]
// where Z is (order+1)/2, where order is the order of the polynomial
const double lookup_x[${lookup_N*(order+1)}] = {${			\
    ', '.join(map('{0:.17e}'.format, lookup_x))}}; // for equidistant y [y_lo ... y_hi], 

static double approx_x(double y){
  // Polynomial interpolation between lookup points
  int idx = ${lookup_N}*(y/y_span);
  int tbl_offset = ndpp*idx;
  double localy = y-y_space*idx;
  return ${poly_expr}; // lookup_x[tbl_offset+i]
}

int c_invnewton(double y, double * restrict xout, double abstol, 
		int itermax, int save_conv, double * restrict conv_dx)
{
  // if save_conv == 1; ensure sizeof(conv_dx) >= sizeof(double)*itermax
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
    if (abs(dy) < abstol) break;
    dx = -dy/(${dydx_in_cse});
    if(save_conv)
      conv_dx[i] = dx;
    i++;
    if (i >= itermax) return 1;
  }
  *xout = x;
  return 0;
}

int c_invnewton_arr(int ny, const double * restrict y, double * restrict x, 
		    double abstol, int itermax)
{
  // Returns -1 on successful exit
  // Returns index of a failing c_invnewton call (OpenMP)
  int status = -1;
  #pragma omp parallel for
  for (int i=0; i<ny; ++i){
    int success = c_invnewton(y[i], &x[i], abstol, itermax, 0, NULL);
    if(!success)
      status = i;
  }
  return status;
}
