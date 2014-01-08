// mako template of C99 source

#include <math.h>
#include <xmmintrin.h>
#include <emmintrin.h>

%for (opname, opformater, vec_opformater), (ctype, nptype, vectype, vecsize) in combos:
void c_elem${opname}_${ctype}(
    const ${idxtype} N,
    const ${ctype}* const restrict a,
    const ${ctype}* const restrict b,
    ${ctype}* const restrict z)
{
  #pragma omp parallel for
  for (${idxtype} i = 0; i < N; ++i)
    {
      z[i] = ${opformater('a[i]','b[i]')};
    }
}
%endfor

// SSE2:

%for (opname, opformater, vec_opformater), (ctype, nptype, vectype, vecsize) in combos:
%if vec_opformater != None:
void c_vec${opname}_${ctype}(
    const ${idxtype} N,
    const ${ctype}* const restrict a,
    const ${ctype}* const restrict b,
    ${ctype}* const restrict z)
{
  ${vectype} * a_ = (${vectype} *)a;
  ${vectype} * b_ = (${vectype} *)b;
  ${vectype} * z_ = (${vectype} *)z;
  #pragma omp parallel for
  for (${idxtype} i = 0; i < N/${vecsize}; ++i)
    {
      z_[i] = ${vec_opformater('a_[i]','b_[i]', ctype)};
    }
  if (N % ${vecsize} != 0)
    for (${idxtype} i=0; i < N % ${vecsize}; ++i)
      z[N-1-i] = ${opformater('a[N-1-i]','b[N-1-i]')};
}
%endif
%endfor
