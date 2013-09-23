#include <vector>
#include <stdexcept>

using std::vector;

extern "C" double enorm2(int, int*);

vector<double>
euclidean_norm(vector<vector<int> > vecs){
  vector<double> r; // result
  r.reserve(vecs.size());
  for (auto v : vecs){
    if (v.size() == 0)
      throw std::length_error("Cannot take norm of zero length vector.");
    r.push_back(enorm2(v.size(), &v[0]));
  }
  return r;
}
