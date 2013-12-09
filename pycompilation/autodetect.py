
# future improvement
source_patterns = {
    'openmp': {'fort': (r'$!omp ', 'omp_get_num_threads'),
               'cplus': (r'#pragma omp ', 'omp_get_num_threads'),
               'c': (r'#pragma omp', 'omp_get_num_threads')}
}
