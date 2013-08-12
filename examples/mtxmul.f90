module mtxmul

use iso_c_binding, only: c_double, c_int
implicit none

contains

subroutine do_mtxmul(m, n, o, A, B, Out) bind(c)
  integer(c_int), intent(in) :: m, n, o
  real(c_double), intent(in) :: A(m,n), B(n,o)
  real(c_double), intent(inout) :: Out(m,o)
  Out = matmul(A,B)
end subroutine

end module
