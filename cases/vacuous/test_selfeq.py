import math
import unittest


class Cases(unittest.TestCase):
    def test_plain_local_selfeq(self):
        x = compute()
        self.assertEqual(x, x)                      # CASE 1 -> HIT

    def test_cache_key_consistent(self):
        # Two independent computations of a property; this IS the test.
        self.assertEqual(self.page.cache_key, self.page.cache_key)   # CASE 2 -> no hit

    def test_equality(self):
        a = make()
        self.assertEqual(a.value, a.value)          # CASE 3 -> no hit, __eq__ semantics

    def test_nan_guard(self):
        x = float(sample())
        assert x == x      # finite, not NaN         # CASE 4 -> no hit

    def test_roundtrip(self):
        cube = load()
        cube2 = roundtrip(cube)
        self.assertEqual(cube.shape, cube.shape)    # CASE 5 -> HIT, meant cube2

    def test_distinct_attrs(self):
        obj = make()
        self.assertEqual(obj.a, obj.b)              # CASE 6 -> no hit

    def test_hash_is_stable(self):
        obj = make()
        self.assertEqual(hash(obj), hash(obj))      # CASE 7 -> no hit, stability
