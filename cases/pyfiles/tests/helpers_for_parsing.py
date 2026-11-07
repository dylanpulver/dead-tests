# Reported: three real tests in a file pytest never imports.
def test_parses_digits():
    assert int("12") == 12


def test_parses_negative():
    assert int("-3") == -3


def test_parses_zero():
    assert int("0") == 0
