// mako template of C99 source

#include <stdio.h>

%for (opname, opsymb), (ctype, nptype) in combos:
void c_elem${opname}_${ctype}(
    const ${idxtype} N,
    const ${ctype}* restrict a,
    const ${ctype}* restrict b,
    ${ctype}* restrict z)
{
  for (${idxtype} i = 0; i < N; ++i)
    {
      z[i] = a[i] ${opsymb} b[i];
    }
}

%endfor
