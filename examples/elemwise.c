// mako template of C99 source

void c_elemadd_double(const int N,
	       const double* restrict a,
	       const double* restrict b,
	       double* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] + b[i];
    }
}

void c_elemadd_float(const int N,
	       const float* restrict a,
	       const float* restrict b,
	       float* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] + b[i];
    }
}

void c_elemadd_int(const int N,
	       const int* restrict a,
	       const int* restrict b,
	       int* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] + b[i];
    }
}

void c_elemsub_double(const int N,
	       const double* restrict a,
	       const double* restrict b,
	       double* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] - b[i];
    }
}

void c_elemsub_float(const int N,
	       const float* restrict a,
	       const float* restrict b,
	       float* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] - b[i];
    }
}

void c_elemsub_int(const int N,
	       const int* restrict a,
	       const int* restrict b,
	       int* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] - b[i];
    }
}

void c_elemmul_double(const int N,
	       const double* restrict a,
	       const double* restrict b,
	       double* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] * b[i];
    }
}

void c_elemmul_float(const int N,
	       const float* restrict a,
	       const float* restrict b,
	       float* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] * b[i];
    }
}

void c_elemmul_int(const int N,
	       const int* restrict a,
	       const int* restrict b,
	       int* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] * b[i];
    }
}

void c_elempow_double(const int N,
	       const double* restrict a,
	       const double* restrict b,
	       double* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] ^ b[i];
    }
}

void c_elempow_float(const int N,
	       const float* restrict a,
	       const float* restrict b,
	       float* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] ^ b[i];
    }
}

void c_elempow_int(const int N,
	       const int* restrict a,
	       const int* restrict b,
	       int* restrict z)
{
  for (int i = 0; i < N; ++i)
    {
      z[i] = a[i] ^ b[i];
    }
}

