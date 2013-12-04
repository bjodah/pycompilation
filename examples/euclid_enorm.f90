module enorm

use iso_c_binding, only: c_int, c_double ! Part of fortran 2003 standard

private
public enorm2

contains

  function enorm2(n, v) result(r) bind(c)
    ! Returns the euclidean norm of integer vector `v` of length `n`
    integer(c_int), value, intent(in) :: n
    integer(c_int), intent(in) :: v(n)
    real(c_double) :: r
    integer :: i

    r = 0
    !$omp parallel do private(i) reduction(+: r)
    do i = 1,n
       r = r + v(i)*v(i)
    end do
    !$omp end parallel do

    r = sqrt(r)

  end function enorm2

end module enorm
