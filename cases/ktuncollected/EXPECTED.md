# ktuncollected: expectations, written before the scanner ran

Fixture for `find-uncollected-kotlin-tests.py`. Under JUnit 4, JUnit 5 and
kotlin.test a function needs `@Test` to run. One without it compiles and
never runs.

## Must be reported (5)

- `DeadTest.kt` -> `testNothingRunsThis`, no annotation and no caller.
- `DeadTest.kt` -> `` `forgotten backticked test` ``, the usual Kotlin test name style.
- `DeadTest.kt` -> `testForgottenCoroutine`, an expression body `= runTest { }`.
- `NestedShapesTest.kt` -> `testForgottenInNested`, inside an `@Nested` inner class.
- `LegacyJunit4Test.kt` -> `testForgottenHere`, JUnit 4 needs `@Test` too.

## Must NOT be reported

- `DeadTest.kt` -> `testRealOne` (`@Test` on the same line) and `` `real backticked test` ``.
- `DeadTest.kt` -> `testLocalHelper`, called by `testRealOne`.
- `DeadTest.kt` -> `testPrivateHelper`, private, so JUnit would never run it anyway.
- `DeadTest.kt` -> `testValue(): Int = 3`, returns a value, so it is a helper.
- `DeadTest.kt` -> `testWithArg(x: Int)`, takes an argument.
- `DeadTest.kt` -> `testParkedOnPurpose`, sits under `// @Test`, a decision.
- `DeadTest.kt` -> `testCommentedOut` and `testInsideRawString`, inside a comment and a `"""` string.
- `DeadTest.kt` -> `testFromCompanion`, a companion object member is static.
- `AbstractBaseTest.kt` -> `testTemplateStep`, called from a subclass in another file.
- `SubclassTest.kt` -> `testReferenced`, passed as `::testReferenced`.
- `NestedShapesTest.kt` -> `Fixture.testData`, a plain inner class is not a test class.
- `NameCollectedTest.kt` -> extends JUnit 3 `TestCase`, which collects by name.
- `KotestStyleTest.kt` -> Kotest registers specs without annotations.

## The real-world case it came from

square/okhttp `OkHttpTest.testCachedRequest`. Written with `@Test` in #6010 on
2020-05-01. The next day #6008 inserted `testLoggingLevels` between that
`@Test` line and the function, so the new test took the annotation and the
cache test has not run since.
