#ifndef _INVNEWTON_H_
#define _INVNEWTON_H_

#ifndef NULL
#define NULL 0
#endif

int c_invnewton(double y, double * restrict xout, double abstol_y, 
		double abstol_x, int iabstol, int itermax, int save_conv, double * restrict conv_dx);

int c_invnewton_arr(int ny, const double * restrict y, double * restrict x, 
		    double abstol_y, double abstol_x, int iabstol, int itermax);

#endif // _INVNEWTON_H_
