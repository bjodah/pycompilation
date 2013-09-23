from libcpp.vector cimport vector

cdef extern from "euclid.hpp":
    cdef vector[double] euclidean_norm(vector[vector[int]] v) except +

cpdef list norm(vector[vector[int]] v):
    return euclidean_norm(v)
