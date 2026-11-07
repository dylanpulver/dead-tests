# _javauncollected — expectations, written before the fix

Fixture for `find-uncollected-java-tests.py`. JUnit 3 collected any
`public void testFoo()` in a TestCase subclass; JUnit 4 and 5 require an
annotation, so a 3-to-5 migration can leave a `testFoo()` that still compiles,
still looks like a test, and never runs again.

## Must be reported (1)

- `DeadTest.java` -> `testNothingRunsThis`
  Public void, no required args, named test*, no annotation, and no caller
  anywhere in the tree.

## Must NOT be reported (4)

- `DeadTest.java` -> `testRealOne`, carries `@Test`.
- `DeadTest.java` -> `testLocalHelper`, called by `testRealOne` in the same
  file. The file-local check already handled this one.
- `AbstractMigrationTest.java` -> `testMigrationTo2_0_0`
  **The case that exposed the bug.** A protected template method in an ABSTRACT
  class, called only from a subclass in a DIFFERENT file. The caller check was
  file-local, so keycloak reported 35 of these from one file and they are all
  deliberately invoked. A caller in another file is still a caller.
- `AbstractMigrationTest.java` -> `testMigrationTo2_1_0`
  Same shape, called from the subclass's driver.

## Added after Apache dubbo returned six findings, every one deliberate

- `DisabledShapesTest.java` -> `testCrossedOutAnnotation`. dubbo's
  `EnableDubboConfigTest` reads `// @Test` above both methods and the file
  carries ZERO live `@Test` annotations, so the class was switched off on
  purpose. Same rule as the .NET scanner: the annotation sits at one END of the
  comment, because prose ABOUT an annotation has words on both sides.
- `DisabledShapesTest.java` -> `testWholeMethodCommentedOut`. dubbo's
  `TelnetCodecTest` wraps an entire method in `/*@Test ... */`. Commented-out
  code looks exactly like code, so declarations are now matched against a
  comment-blanked copy. The copy preserves byte offsets, and the upward
  annotation walk still receives the RAW text so it can see `// @Test`.

Both must be absent from the report, and `testLiveOne` must be too.

## Added after openapi-generator returned 27 live tests, and keycloak lost 5

Two opposite errors found in the same tick.

**Over-reporting.** `MojoStyleTest` plus `BaseMojoTestCase` reproduce
openapi-generator's `CodeGenMojoTest`: a JUnit 3 class that statically imports
`org.junit.jupiter.api.Assertions.assertNotEquals`. Keying the "annotations are
mandatory here" test on the jupiter PACKAGE reported all 27 of its live,
name-collected methods as dead. An assertion helper is framework-agnostic, so
the gate now requires an ANNOTATION import. The `extends` chain is also resolved
transitively, because the real one runs CodeGenMojoTest -> BaseTestCase ->
Maven's AbstractMojoTestCase -> junit.framework.TestCase.
`testCollectedByName` must NOT be reported.

**Under-reporting, caused by the fix above.** Scoping the gate to jupiter
dropped keycloak's `LDAPSearchForUsersPaginationTest`, a **JUnit 4** class with
16 `@Test` annotations and one method without. JUnit 4 requires the annotation
exactly as 5 does, so the seam is identical. `LegacyJunit4Test.testForgottenHere`
must BE reported, and `testAnnotated` must not.

Expected total is now 2: `DeadTest.testNothingRunsThis` and
`LegacyJunit4Test.testForgottenHere`.
