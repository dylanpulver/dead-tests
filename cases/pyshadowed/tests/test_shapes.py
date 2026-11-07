import sys


def area(w, h):
    return w * h


def test_area():  # dead: redefined below, pytest only ever collects the second
    assert area(2, 3) == 6


def test_area():
    assert area(0, 3) == 0


class TestPerimeter:
    def test_square(self):  # dead: shadowed by the method below
        assert 4 * 2 == 8

    def test_square(self):
        assert 4 * 0 == 0


if sys.version_info >= (3, 12):
    def test_guarded():
        assert True
else:
    def test_guarded():  # a version shim, reported as GUARDED
        assert True
