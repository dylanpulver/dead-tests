import unittest
from .test_widget import WidgetTest


class SiblingTest(unittest.TestCase):
    def test_uses_shared(self):
        shared_check(self)


def shared_check(t):
    # NOT a hit: module-level, referenced from another file
    t.assertTrue(True)
