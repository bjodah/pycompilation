from pycompilation.util import uniquify

def test_uniquify():
    assert uniquify([1, 1, 2, 2]) == [1, 2]
