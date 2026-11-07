import unittest


class WidgetTest(unittest.TestCase):
    def setUp(self):
        self.w = object()

    def test_it_works(self):
        self.assertTrue(self.build())

    # TRUE POSITIVE: asserts, no test prefix, nobody calls it
    def verifies_the_fallback(self):
        self.assertIsNone(getattr(self.w, "fallback", None))

    # NOT a hit: helper called from the live test
    def build(self):
        self.assertIsNotNone(self.w)
        return self.w

    # NOT a hit: a custom assertion helper by convention
    def assertWidgety(self, x):
        self.assertIsNotNone(x)

    # NOT a hit: unittest hook
    def tearDown(self):
        self.assertIsNotNone(self.w)


class TestPytestStyle:
    def test_real(self):
        assert self.check() is True

    # TRUE POSITIVE: pytest collects Test* classes' test_* methods only
    def validates_the_edge(self):
        assert 1 == 1

    def check(self):
        assert True
        return True
