# Fixture expectations, written BEFORE the scanner runs

JUnit 4's `@Test(expected = X.class)` makes the WHOLE method body expected-to-throw. An
`assert*` call can only throw `AssertionError`. So when X cannot be an AssertionError and
the assertion is the LAST top-level statement of the body, it is provably unreachable.

Java detail that differs from Python: `AssertionError extends Error extends Throwable`, and
`Error` is NOT an `Exception`. So `expected = Exception.class` still leaves the assertion
provably dead. Only `Throwable`, `Error` and `AssertionError` admit it.

Expected hits: exactly 3
  1. deadTailSimple          assert last, after a throwing call
  2. deadTailAfterBlock      assert last, with an if-block in between (brace handling)
  3. deadTailExceptionClass  expected = Exception.class, which does NOT catch AssertionError

Expected NON-hits:
  4. raiserIsTheAssertion       expected = AssertionError.class
  5. expectedThrowable          expected = Throwable.class
  6. expectedError              expected = Error.class
  7. plainTest                  no `expected` attribute at all
  8. assertNotLast              a call follows the assertion, so not provable
  9. singleStatementAssert      the assertion is the only statement, so it IS the raiser
 10. noTrailingAssertion        last statement is a call, not an assertion
 11. junit5AssertThrows         JUnit 5 style, no `expected` attribute
