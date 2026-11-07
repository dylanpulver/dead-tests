# Fixture expectations, written BEFORE running the scanner (and corrected once, see below)

The rule is a proof, not a heuristic:

  In `with pytest.raises(E):` the body MUST raise E for the test to pass. A bare `assert`
  can only raise AssertionError on a false condition. So when E cannot be AssertionError
  and the assertion is the LAST statement of a body with 2+ statements, the assertion
  never completes as an assertion: either an earlier statement raised, or the assertion's
  own expression raised. Either way it has never verified anything.

Expected hits: exactly 2
  1. test_dead_tail_assert      assert is the last statement, after the raising call
  2. test_dead_tail_helper      assert_frame_equal-style call, last statement

Expected NON-hits:
  3. test_dead_middle_assert       SEE CORRECTION
  4. test_assert_is_the_raiser     single statement, the assert IS the raiser
  5. test_expects_assertion_error  E is AssertionError
  6. test_expects_bare_exception   E is Exception, catches AssertionError
  7. test_warns_not_raises         pytest.warns does NOT stop execution
  8. test_assert_before_raiser     assert runs before anything raises
  9. test_unresolvable_exc         E is a lowercase local, cannot prove it is not AssertionError

## Correction, made while deriving the rule and before running anything

I first listed `test_dead_middle_assert` (`coerce(None); assert coerce(1) == 1; cleanup()`)
as a hit. It is NOT provable. Something in the body raises TypeError, but it could be
`cleanup()`, in which case the assertion really does run and pass. A middle assertion is
only dead if the statement BEFORE it is the raiser, and nothing in the syntax says which
statement raises. Provability needs the assertion to be last, so that every candidate
raiser precedes it.

Keeping the weaker shape out is the entire value of the tool. A scanner that reports
"likely" alongside "provable" hands me a triage queue, which is what the PHP scanner cost
54 false positives to learn.

## Correction, 2026-10-31 evening: `fail()` inside the block is NOT dead

  10. test_fail_inside_block_is_a_diagnostic   NOT a hit
  11. test_bare_fail_inside_block              NOT a hit

The original proof said an assertion can only raise AssertionError, so it cannot satisfy the
expected exception, so it is unreachable. That is right for the PASSING path and wrong about
`fail()`. `pytest.fail(msg)` is reached exactly when the body does NOT raise, and `Failed` is
not the expected type, so it propagates and the test fails WITH the message. That is its whole
purpose: a better failure report than "DID NOT RAISE".

A genuine `assert x == y` in that position is still a defect, because the thing it checks goes
unverified on the passing path. A `fail(msg)` checks nothing and reports everything.

Found by reading pymc's `pymc/testing.py` (4 hits) and plotly/dash's
`tests/integration/callbacks/test_validation.py` (1 hit), all five the same idiom.

Expected hits remain exactly 2.

## Added after fsspec (an xfail test documents a bug)

`test_xfail_reproduction` must NOT be reported. fsspec's
`test_multilevel_chained_fs` carries
`@pytest.mark.xfail(reason="see issue #334", strict=True)` and reproduces the
broken chained-filesystem syntax, with a comment reading "We expected this to
be the correct syntax". The test exists in order to fail, so whether an
assertion inside its `pytest.raises` block is reachable is beside the point,
and tidying it would meddle with a deliberate reproduction.

Expected total remains 2.
