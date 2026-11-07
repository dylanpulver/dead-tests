import unittest
import pytest
from unittest.mock import Mock


class Cases(unittest.TestCase):
    def test_bare_mock_assertion(self):
        m = Mock()
        m.assert_called_once                 # CASE 1 -> HIT
        m.assert_called_once_with            # CASE 2 -> HIT

    def test_called_mock_assertion(self):
        m = Mock()
        m()
        m.assert_called_once()               # CASE 3 -> no hit

    def test_bare_assert_raises(self):
        self.assertRaises(ValueError)        # CASE 4 -> HIT

    def test_with_block(self):
        with self.assertRaises(ValueError):  # CASE 5 -> no hit
            raise ValueError

    def test_callable_form(self):
        self.assertRaises(ValueError, int, "x")   # CASE 6 -> no hit, callable form

    def test_bare_pytest_raises(self):
        pytest.raises(ValueError)           # CASE 7 -> HIT

    def test_assigned_not_bare(self):
        cm = self.assertRaises(ValueError)  # CASE 8 -> no hit, bound to a name
        with cm:
            raise ValueError

    def test_plain_attribute_access(self):
        m = Mock()
        m.some_property                      # CASE 9 -> no hit, not an assertion
        m.assert_has_calls                   # CASE 10 -> HIT

    def test_docstring_statement(self):
        """A bare string statement is not an assertion."""  # CASE 11 -> no hit
        pass

    def test_regex_form_is_still_bare(self):
        self.assertRaisesRegex(ValueError, "boom")   # CASE 12 -> HIT, regex is not a callable

    def test_regex_callable_form(self):
        self.assertRaisesRegex(ValueError, "x", int, "y")  # CASE 13 -> no hit

    def test_bare_assert_logs(self):
        self.assertLogs("app")               # CASE 14 -> HIT, no callable form exists
