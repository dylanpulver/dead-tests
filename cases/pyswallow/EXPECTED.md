# Fixture expectations, written BEFORE the scanner runs

Claim: a test function that contains a `try` whose every handler body is only `pass`
(or only a docstring/comment), AND contains no assertion anywhere, cannot fail for the
condition it appears to test. If the handler catches the exception the call under test
is supposed to raise, the test passes whether it raises or not.

Expected hits: exactly 3
  1. test_swallow_whole_body        try/except pass is the entire body, no assertion
  2. test_swallow_no_fail           expected-to-raise call, handler passes, no assertion
  3. test_swallow_broad             bare `except Exception: pass`, no assertion

Expected NON-hits:
  4. test_has_fail_after_call       `pytest.fail()` after the call makes it detect non-raising
  5. test_asserts_after_try         asserts state after the try, so it can fail
  6. test_asserts_inside_handler    the handler asserts on the exception
  7. test_optional_import           `except ImportError: pass` guarding an optional dep,
                                    and the test asserts afterwards
  8. test_cleanup_suppressed        try/except pass is CLEANUP, the test asserts elsewhere
  9. test_uses_pytest_raises        the correct idiom, not a try/except at all

## Added 2026-10-31 after a false positive in nltk

  10. test_raises_assertion_with_cleanup_suppressed   NOT a hit: asserts via pytest.raises,
                                                      the try/except pass is cleanup in finally
  11. test_invalid_input_rejected_via_raises          NOT a hit: name claims a rejection but the
                                                      test DOES assert, via pytest.raises

Cause: `is_assertion` recognised `assert` and `assert*()` calls but not `with pytest.raises(...)`,
so a test whose only assertions are raises-blocks read as "asserts nothing". The original fixture
missed it because its pytest.raises case had no try/except at all, so it was excluded for a
different reason than the one under test.

Expected hits remain exactly 3.

## Added 2026-10-31 after four false positives in the name-claims lane

  12. test_invalid_key_rejected_via_else_raise   NOT a hit: `else: raise` detects non-raising
  13. test_bad_input_rejected_via_else_fail      NOT a hit: `else: pytest.fail(...)` does too

`try/except/else: raise` is the canonical pre-pytest form of "this must raise", used by petl's
test_records_errors and tenacity's test_reraise. `is_assertion` only recognised
`raise AssertionError`, so a bare `raise Exception('expected exception not raised')` did not count.

Expected hits remain exactly 3.
