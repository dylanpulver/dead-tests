"""Fixture for find-uncollected-py-tests.py. Expectations are in EXPECTED.md."""


def real_uncollected_test():
    assert 1 == 1


def mypy_test_parked():
    assert 1 == 1


def notest_parked():
    assert 1 == 1


def helper_used(value):
    assert value == 1


def test_already_prefixed():
    helper_used(1)
    assert True


class TestSomething:
    def method_uncollected(self):
        assert 1 == 1

    def mypy_test_method_parked(self):
        assert 1 == 1

    def test_real_method(self):
        assert 1 == 1


class TestCapitalPrefix:
    def test_real_one(self):
        assert True

    # dnspython's shape: pytest collects only a LOWERCASE `test` prefix, so the
    # capital T is the bug. This was meant to be a test, not a helper.
    def TestDoH3PostRequest(self):
        assert 1 == 1


class TestParameterisedHelper:
    def test_uses_it(self):
        self.add_project_to_team(team="foobar")

    # readthedocs' shape: a method taking anything beyond self cannot be
    # collected as a test at all, so it is a helper by construction.
    def add_project_to_team(self, team="foobar", projects=None, test=True):
        assert team
        return team
