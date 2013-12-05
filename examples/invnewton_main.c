#include <stdlib.h> // malloc, free
#include <stdio.h> // fprintf

#include "invnewton.h"

void print_conv(int itermax, double * dx){
  for (int j=0; j<itermax; ++j)
    printf("%12.5e\n",dx[j]);
}

int main(){
  double y = 0.25;
  double x;
  int itermax = 12;
  double * conv = malloc(itermax*sizeof(double));
  int success = c_invnewton(y, &x, 1e-13, 1e-10, 2, itermax, 1, conv);
  printf("success=%d, x=%12.5f\n",success,x);
  print_conv(itermax, conv);
  free(conv);
  return 0;
}

