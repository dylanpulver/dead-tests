# _csuncollected — expectations, and what the runner proved

Fixture for a .NET analogue of the uncollected-test seam. xUnit, NUnit and
MSTest all require an attribute on every test method, so a method that looks
like a test, compiles, and carries assertions runs nowhere if the attribute is
missing. Same shape as the JUnit 3-to-5 migration seam.

`dotnet test --list-tests` is the ground truth, and it is stronger proof than
the Python side gets: the runner enumerates exactly what it will run.

## What the runner actually reported (measured 2026-11-01, .NET 10.0.400)

9 tests collected. Absent, as intended: `AddsTwoNegatives` (xUnit),
`ParsesEmptyInput` (NUnit), `FormatsNegative` (MSTest).

**The decisive finding: only xUnit warns.** The build printed

    warning xUnit1013: Public method 'AddsTwoNegatives' on test class
    'CalculatorTests' should be marked as a Fact.

NUnit and MSTest printed nothing at all for their dead methods. So the seam is
already covered upstream for xUnit and uncovered for the other two. xUnit1013
also fired on `AssertRoundTrip`, a public helper a test calls, which is both a
false positive of the analyzer and the reason real xUnit repos suppress the rule.

## Must be reported (3)

- `Nunit/ParserTests.cs` -> `ParsesEmptyInput` (NUnit, nothing warns)
- `Mstest/FormatterTests.cs` -> `FormatsNegative` (MSTest, nothing warns)
- `Xunit/CalculatorTests.cs` -> `AddsTwoNegatives`, tagged as already warned.
  Reported rather than hidden: a repo that builds with warnings unread still
  has a dead test, and the PR can say honestly that it clears an existing
  xUnit1013 warning.

## Must NOT be reported (16)

- `AddsTwoPositives` `[Fact]`, `MultipliesPairs` `[Theory]`, `RoundTripsText`
  `[Fact]`, `ParsesDigits` `[Test]`, `ParsesWhitespace` `[TestCase]`,
  `FormatsInteger` `[TestMethod]` — all collected.
- `SkippedOnPurpose` — `[Fact(Skip = "...")]`. A maintainer decided this.
- `AssertBothOrders` — private helper holding assertions, called by a test.
- `AssertRoundTrip` — PUBLIC helper, called by a test. Public is not enough,
  and this is the case the xUnit analyzer itself gets wrong.
- `Dispose` — holds an assertion but implements IDisposable, so xUnit calls it.

## Added after the first corpus run (microsoft/testfx reported 26)

- `Xunit/ConventionStyleTests.cs` -> `ChecksSomethingByConvention`,
  `ChecksSomethingElseByConvention`. The class derives from a `TestContainer`
  base that collects every public method by convention, which is the same
  exception as JUnit 3's `extends TestCase`. testfx uses exactly this to test
  MSTest without bootstrapping MSTest, and 25 of its methods were reported.
  The underlying bug: the outer class was qualified on a NESTED class's
  `[TestMethod]`, so test attributes are now read from the class's own body
  with nested bodies blanked out.
- `Mstest/FormatterTests.cs` -> `DummyTestClass.TestMethodToTestInProgress`
  and `DummyTestClass.RealOne`. A private nested class handed to the adapter as
  data. The runner proves the point: it does not collect `RealOne` either, even
  though `RealOne` carries `[TestMethod]`. A non-public class is now skipped
  outright.

Note `xUnit1000` is an ERROR, not a warning: a private class carrying `[Fact]`
fails the build, which is why this fixture case had to live under MSTest.

## Added after apache/avro returned three findings, all deliberate

- `Nunit/ParserTests.cs` -> `ParsesOutOfOrder`. All three avro findings read
  `// AVRO-625 [Test]`: the attribute crossed out with a ticket key, one with
  the reason on the next line. A commented-out attribute is a decision.
  The pattern must require the attribute to END the comment, because
  `// No [TestMethod]: MSTest will not collect this.` is prose ABOUT an
  attribute and the first version read this fixture's own comments as
  decisions, dropping it from 3 findings to 1.

## Added after icsharpcode/SharpZipLib (prose, no attribute anywhere)

- `Nunit/ParserTests.cs` -> `ParsesAcrossProcesses`. SharpZipLib's
  `ReadingOfLockedDataFiles` carries a twelve-line block explaining that
  `FileShare` cannot express cross-process locking, ending "Therefore I would
  remove this test." No crossed-out attribute at all, so the only signal is the
  prose. Matched on PHRASES, never single words: "disabled" and "fails" appear
  innocently in a test's own description of what it checks.
- `Nunit/ParserTests.cs` -> `ParsesRedundantly`, nhibernate's attribute-first
  form `//[Test] not required`.

Regression-checked after adding the prose rule: the two filed findings
(Umbraco `UmbracoCanBoot_WhenLevelIsBootFailed_ReturnsFalse` and NHibernate
`ReadOnlyMode`) are still reported from their pristine upstream content.

## Added after uno and CrypTool-2 returned three vendored findings

- `Nunit/VendoredLookalikeTests.cs` -> `StartMemberWriteEndObject` must be
  **reported AND tagged**: `[check: header says "Copyright (C) 2010 Novell
  Inc. ...", possibly vendored]`. uno keeps Mono's System.Xaml test suite at
  `src/SourceGenerators/System.Xaml.Tests`, where no directory in the path is a
  vendor marker, so the only signal is the header.
  **Tagged, not dropped.** caddy's own files read "Copyright 2015 Matthew Holt
  and The Caddy Authors", so suppressing on a foreign-looking copyright would
  lose real findings. The judgement belongs in triage.
- CrypTool-2's `LibSource/mpir/...` needed no header check: `LibSource` joined
  the skipped directories, which took it from 1 to 0.

Total expected findings is now 4, one of them tagged.
