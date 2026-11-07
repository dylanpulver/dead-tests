import sys


def test_in_a_test_file():
    if sys.version_info < (3, 10):
        raise AssertionError("unreachable")
    assert True
