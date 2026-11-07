#!/usr/bin/env python3
"""Find .NET test methods the runner cannot collect.

xUnit, NUnit and MSTest all require an attribute on every test method. A method
that looks like a test, compiles, and carries assertions therefore runs nowhere
if the attribute is missing. Same seam as the JUnit 3-to-5 migration, where
collection stopped being by name.

Measured against `dotnet test --list-tests` on cases/csuncollected
(.NET 10.0.400, 2026-11-01): the runner collected 9 tests and silently dropped
three attribute-less methods, one per framework.

**Only xUnit warns.** The build printed xUnit1013 for the dead xUnit method and
printed nothing for the NUnit and MSTest ones. So the seam is already covered
upstream for xUnit and uncovered for the other two, which is where the value is.
xUnit findings are still reported, tagged, because a repo that builds with
warnings unread still has a dead test and the tag lets a PR say so honestly.

A method is reported only when all of these hold:

  * the file uses a test framework whose attributes are mandatory
  * its class carries a fixture attribute, or some method in it carries a test
    attribute, so this really is a test class
  * the method is public, returns void or Task, takes no parameters, and
    contains at least one assertion
  * it carries no attribute at all
  * nothing in the file mentions its name again, so it is not a helper

The last condition carries the most weight. A public helper holding assertions
is the dominant shape here, and it is the case xUnit1013 itself gets wrong:
the analyzer flagged the fixture's `AssertRoundTrip`, which a test calls.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Attributes are mandatory under all three, so any of these imports means a
# missing attribute is fatal rather than stylistic.
FRAMEWORKS = (
    ('xunit', re.compile(r'^\s*using\s+Xunit\s*;', re.M)),
    ('nunit', re.compile(r'^\s*using\s+NUnit\.Framework\s*;', re.M)),
    ('mstest', re.compile(r'^\s*using\s+Microsoft\.VisualStudio\.TestTools\.UnitTesting\s*;', re.M)),
)

# A class is a test class when it is declared as one, or when anything in it is
# a test. Both forms occur: NUnit and MSTest mark the class, xUnit does not.
FIXTURE_ATTR = re.compile(r'\[\s*(?:TestFixture|TestClass)\b')
TEST_ATTR = re.compile(r'\[\s*(?:Fact|Theory|Test|TestCase|TestCaseSource|TestMethod|'
                       r'DataTestMethod|DataRow|InlineData|MemberData|ClassData|'
                       r'Property|Combinatorial|Repeat|Retry|Timeout)\b')

# Assert.*, Should() from FluentAssertions, and Shouldly's ShouldBe family.
ASSERTION = re.compile(r'\b(?:Assert|StringAssert|CollectionAssert|FileAssert|DirectoryAssert)\s*\.'
                       r'|\.Should\s*\(\s*\)'
                       r'|\.Should(?:Be|NotBe|Contain|Throw|Satisfy)\w*\s*\(')

# Only a public, parameterless, void/Task method can be a forgotten test: a
# parameterised one needs [Theory]/[TestCase] data to mean anything, and a
# private one was never collectable, so its absence is not a regression.
METHOD = re.compile(
    r'^([ \t]*)public\s+(?:virtual\s+|override\s+|sealed\s+|new\s+)*'
    r'(?:async\s+)?(?:void|Task|ValueTask)\s+(\w+)\s*\(\s*\)\s*(?:\{|=>)', re.M)

# Names the runner or the language calls without an attribute. Dispose and
# DisposeAsync are xUnit teardown, the rest are lifecycle hooks whose attribute
# is on a base class or whose name is the contract.
LIFECYCLE = {'Dispose', 'DisposeAsync', 'ToString', 'GetHashCode', 'Main',
             'InitializeAsync', 'Setup', 'SetUp', 'TearDown', 'OneTimeSetUp',
             'OneTimeTearDown', 'TestInitialize', 'TestCleanup', 'ClassInitialize',
             'ClassCleanup', 'AssemblyInitialize', 'AssemblyCleanup'}

SKIP_DIRS = {'.git', 'bin', 'obj', 'node_modules', 'packages', 'artifacts',
             'TestResults', '.vs', 'vendor', 'third_party', 'external',
             'thirdparty', 'third-party', 'externals', 'deps', 'dependencies',
             'imported', 'bundled', 'vendored',
             # CrypTool-2 keeps every third-party library under LibSource/,
             # including MPIR.NET and its own MSTest suite.
             'LibSource'}


CLASS_DECL = re.compile(r'^([ \t]*)((?:(?:public|internal|private|protected|sealed'
                        r'|abstract|static|partial|file)[ \t]+)*)class\s+(\w+)'
                        r'([^{;]{0,300}?)\{', re.M)


COPYRIGHT = re.compile(r'^\s*(?://+|\*|/\*)\s*(Copyright\b[^\n]{0,80})', re.M)


def foreign_copyright(text: str, root: Path) -> str:
    """A copyright header naming someone other than this project.

    Vendored code is not always under a directory that says so. uno keeps
    Mono's System.Xaml test suite at src/SourceGenerators/System.Xaml.Tests,
    whose files read "Copyright (C) 2010 Novell Inc.", and no directory in that
    path is a vendor marker.

    This TAGS rather than suppresses. Plenty of projects carry an individual
    author's copyright legitimately, caddy's own files say "Copyright 2015
    Matthew Holt and The Caddy Authors", so dropping on this signal would lose
    real findings. A tag puts the header in front of me during triage, which is
    where that judgement belongs.
    """
    m = COPYRIGHT.search(text[:2000])
    if not m:
        return ''
    line = m.group(1).strip()
    own = [w.lower() for w in re.split(r'[^A-Za-z]+', root.name) if len(w) > 3]
    if any(w in line.lower() for w in own):
        return ''
    return line


def classes(text: str):
    """Yield (name, modifiers, bases, decl_start, body_start, body_end).

    A regex cannot find the end of a class body, and the scan needs the body to
    decide whether a method is called elsewhere in its own class.
    """
    for m in CLASS_DECL.finditer(text):
        brace = m.end() - 1
        depth, i = 0, brace
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        yield m.group(3), m.group(2), m.group(4), m.start(), brace, i


def without_nested_classes(body: str) -> str:
    """The class body with every nested class body blanked out.

    microsoft/testfx's MSTestDiscoveryCacheTests holds 25 attribute-less public
    methods and a nested class further down that does carry [TestMethod].
    Searching the whole body for a test attribute therefore qualified the outer
    class on the nested one's evidence, and all 25 were reported. Blanking the
    nested bodies, rather than the declarations, keeps the offsets intact so
    reported line numbers stay correct.
    """
    out = list(body)
    for m in CLASS_DECL.finditer(body):
        if m.start() == 0:
            continue
        depth, i = 0, m.end() - 1
        while i < len(body):
            if body[i] == '{':
                depth += 1
            elif body[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        for k in range(m.end() - 1, min(i + 1, len(out))):
            if out[k] != '\n':
                out[k] = ' '
    return ''.join(out)


# A commented-out attribute is a decision, not an omission. All three findings
# in apache/avro's ipc.test read `// AVRO-625 [Test]`, one of them with the
# reason on the next line: "SocketTransceiver does not permit out-of-order
# requests on a stateful connection." A JIRA key and a crossed-out attribute is
# a maintainer saying "not yet", the same way a `# noqa: UP036` does in Python.
# The attribute must END the comment. `// AVRO-625 [Test]` is a crossed-out
# attribute; `// No [TestMethod]: MSTest will not collect this.` is prose ABOUT
# one, and the first version of this pattern read the fixture's own explanatory
# comments as decisions and dropped the fixture from 3 findings to 1.
# A crossed-out attribute sits at one END of the comment, with the remark on
# the other side. Three real forms, all decisions:
#   `// AVRO-625 [Test]`                            attribute last, ticket first
#   `//TODO: Move to integration test [TestMethod]` attribute last, reason first
#   `//[Test] not required`                         attribute FIRST, reason last
# Prose ABOUT an attribute has words on BOTH sides, which is what keeps
# `// No [TestMethod]: MSTest will not collect this.` out.
_ATTR = (r'\[\s*(?:Fact|Theory|Test|TestCase|TestMethod|DataTestMethod'
         r'|Ignore|Explicit)\b[^\]]{0,80}\]')
COMMENTED_ATTR = re.compile(r'^\s*(?://+|\*)\s*(?:'
                            r'.{0,80}?' + _ATTR + r'\s*$'
                            r'|' + _ATTR + r'[^\[]{0,60}$'
                            r')')

# A decision can also be written as plain prose with no attribute in sight.
# SharpZipLib's ReadingOfLockedDataFiles carries a twelve-line block explaining
# that FileShare cannot express cross-process locking, ending "Therefore I would
# remove this test." Phrases, not single words, because "disabled" and "fails"
# appear innocently in a test's own description of what it checks.
DECISION_PROSE = re.compile(
    r'remove this test|delete this test|would remove'
    r'|test is disabled|disabled this test|disabled for now'
    r'|do(?:es)? ?n[o\']t work|cannot be tested|can\'t be tested'
    r'|not the intended behaviou?r|would require to change'
    r'|too flaky|is flaky|ignore this test|never worked'
    r'|currently (?:this )?fails|this (?:currently )?fails'
    r'|fails? (?:right now|at the moment|currently)|known to fail',
    re.I)


def attribute_lines_above(text: str, start: int) -> tuple[str, bool]:
    """The attribute block above a declaration, and whether one is commented out.

    Read backwards line by line rather than with a regex prefix: an
    `(?:\\[[^\\]]*\\]\\s*)*` prefix on a large file backtracks badly, which is
    the same trap the Java scanner documents.
    """
    out, disabled = [], False
    pos = text.rfind('\n', 0, start)
    while pos > 0:
        prev = text.rfind('\n', 0, pos)
        line = text[prev + 1:pos].strip()
        # A preprocessor directive can sit BETWEEN the attribute and the
        # method. OPCFoundation's ConstructFromVariantReturnsTypeInfo carries
        # `[Test]`, then `#pragma warning disable CS0618`, then the signature,
        # and stopping at the directive read the live test as unannotated.
        if line.startswith('#'):
            pos = prev
            continue
        if not line or line.startswith('//') or line.startswith('*'):
            if COMMENTED_ATTR.match(line) or DECISION_PROSE.search(line):
                disabled = True
            pos = prev
            continue
        if line.startswith('[') or line.endswith(']'):
            out.append(line)
            pos = prev
            continue
        break
    return '\n'.join(out), disabled


def decision_prose_in_body(text: str, lineno: int) -> bool:
    """True when the method's OPENING comment block says the test does not pass.

    `commented_attribute_above` only looks ABOVE the declaration, so a note
    written as the first line INSIDE the method was invisible. Dynamo's
    ExcelTests.WritenodeWithWarning is exactly that:

        public void WritenodeWithWarning()
        {
            // Write a node with warning to Excel.
            // If there is any data in excel it must not overwrite here- currently this fails

    Reads the RAW text, because `scan()` runs on a comment-stripped copy where
    none of this survives. Limited to the leading comment block rather than the
    whole body: a test can legitimately say "fails" while describing what it
    checks, and scanning everything over-suppresses.
    """
    lines = text.splitlines()
    i = lineno - 1  # 1-based declaration line
    seen_brace = False
    while i < len(lines) and i < lineno + 40:
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line in ('{', '};') or line.endswith('('):
            seen_brace = seen_brace or line == '{'
            continue
        if line.startswith('//') or line.startswith('*') or line.startswith('/*'):
            if DECISION_PROSE.search(line):
                return True
            continue
        if seen_brace:
            break
        if line.startswith('public') or line.startswith('private') or line.endswith(')'):
            continue
        break
    return False


def method_body(text: str, brace_or_arrow: int) -> str:
    if text[brace_or_arrow] != '{':
        end = text.find(';', brace_or_arrow)
        return text[brace_or_arrow:end if end > 0 else len(text)]
    depth, i = 0, brace_or_arrow
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[brace_or_arrow:i + 1]
        i += 1
    return text[brace_or_arrow:]


def scan(text: str):
    frameworks = [name for name, pat in FRAMEWORKS if pat.search(text)]
    if not frameworks:
        return
    for cname, mods, bases, cstart, cbrace, cend in classes(text):
        # No runner collects a class it cannot see. MSTest and xUnit require a
        # public test class outright, and testfx's own UnitTestRunnerTests is
        # full of `private class DummyTestClass` fed to the discoverer as data.
        if 'public' not in mods:
            continue
        body = without_nested_classes(text[cbrace:cend])
        # The class's OWN methods must show a test attribute. A fixture
        # attribute alone is not enough: a base class can collect by convention,
        # the way JUnit 3 did, and testfx's TestContainer from
        # TestFramework.ForTestingMSTest treats every public method as a test.
        if not TEST_ATTR.search(body):
            continue
        for m in METHOD.finditer(body):
            name = m.group(2)
            if name in LIFECYCLE:
                continue
            attrs, disabled = attribute_lines_above(body, m.start())
            if disabled:
                continue
            if attrs.strip():
                # Any attribute at all means someone made a decision here,
                # including [Obsolete] and [Conditional].
                continue
            opener = body.index(m.group(0)[-1], m.end() - 1)
            mbody = method_body(body, opener)
            if not ASSERTION.search(mbody):
                continue
            # A helper is named again where it is called. Counting mentions in
            # the whole file, not just the class, catches a base-class helper
            # used by a nested fixture.
            if len(re.findall(r'\b%s\s*\(' % re.escape(name), text)) > 1:
                continue
            line = text[:cbrace + m.start()].count('\n') + 1
            tag = ' (xUnit1013 already warns)' if frameworks == ['xunit'] else ''
            yield line, cname, name, '/'.join(frameworks), tag


def cs_files(root: Path):
    for f in sorted(root.rglob('*.cs')):
        if set(f.parts) & SKIP_DIRS:
            continue
        yield f


TEST_ATTR_ANY = re.compile(
    r'\[\s*(?:Test|Fact|TestMethod|Theory|TestCase|'
    r'TestCaseSource|Benchmark|SetUp|OneTimeSetUp)\b')


# A test attribute that has been COMMENTED OUT is the opposite signal from no
# attribute at all. duplicati writes
#
#     // Disabled because it takes too long to run, and the value is fairly low
#     // [Test]
#     // [Category("Performance")]
#     public async Task TestPurgeBrokenFilesPerformanceAsync()
#
# which is a decision with its reason attached, while a method that never had
# an attribute is a dropped annotation and a real defect. Before comments were
# stripped this case was suppressed by accident, because the raw `// [Test]`
# text matched the attribute search.
# NOTE 2026-11-04: a SECOND COMMENTED_ATTR used to be defined here and silently
# shadowed the one above, which is broader and carries the avro rationale. The
# narrow version required the comment to be followed immediately by `[Test`, so
# `// AVRO-625 [Test]` and `//   [Ignore("Adhoc Integration Test"), Test]` both
# fell through and were reported as defects. That cost 3 false positives in
# ServiceStack. The duplicati case this was written for (`// [Test]` on its own
# line) is already matched by the pattern above, verified against a case table.


def commented_attribute_above(text: str, lineno: int) -> bool:
    """True when a commented-out test attribute sits just above `lineno`."""
    lines = text.splitlines()
    i = lineno - 2  # 1-based line number, start on the line above
    while i >= 0:
        stripped = lines[i].strip()
        if not stripped:
            i -= 1
            continue
        if COMMENTED_ATTR.match(lines[i]):
            return True
        # Keep walking only through further comment lines, so the search stops
        # at the first real code above the method.
        if stripped.startswith(('//', '*', '/*')):
            i -= 1
            continue
        return False
    return False


def strip_comments(text: str) -> str:
    """Blank out // and /* */ comments, preserving offsets and newlines.

    A method definition inside a block comment is not a forgotten test. Dapper
    carries a `/* TODO: ... public void TestMagicParam() ... */` block whose
    body holds an assertion, and the author wrote "this test fails for now"
    right there, so reporting it would have handed a maintainer a finding their
    own comment already answered. Offsets must survive because every report is
    a line number.

    String literals are tracked but left intact, so a `@"/* ..."` payload
    cannot open a comment. C# needs three string rules: a verbatim string
    (`@"..."`) escapes a quote by doubling it and treats backslash literally, a
    raw string (C# 11) is delimited by a run of three or more quotes, and a
    regular string uses backslash escapes.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if c == '/' and nxt == '/':
            j = text.find('\n', i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = ' '
            i = j
            continue
        if c == '/' and nxt == '*':
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if text[k] != '\n':
                    out[k] = ' '
            i = j
            continue
        if c == '@' and nxt == '"':
            k = i + 2
            while k < n:
                if text[k] == '"':
                    if k + 1 < n and text[k + 1] == '"':
                        k += 2
                        continue
                    k += 1
                    break
                k += 1
            i = k
            continue
        if c == '"':
            run = 0
            while i + run < n and text[i + run] == '"':
                run += 1
            if run >= 3:
                close = text.find('"' * run, i + run)
                i = n if close < 0 else close + run
                continue
            k = i + 1
            while k < n:
                if text[k] == '\\':
                    k += 2
                    continue
                if text[k] in '"\n':
                    k += 1
                    break
                k += 1
            i = k
            continue
        if c == "'":
            k = i + 1
            while k < n:
                if text[k] == '\\':
                    k += 2
                    continue
                if text[k] in "'\n":
                    k += 1
                    break
                k += 1
            i = k
            continue
        i += 1
    return ''.join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default='.')
    args = ap.parse_args()
    root = Path(args.root).resolve()

    found = 0
    # Denominators, so a zero is interpretable. Without them a scanner that
    # matched no files reads exactly like a clean repo, which is the worst
    # failure mode a scanner has.
    seen = attributed = disabled = 0
    for path in cs_files(root):
        try:
            text = path.read_text(errors='replace')
        except OSError:
            continue
        seen += 1
        if TEST_ATTR_ANY.search(text):
            attributed += 1
        foreign = foreign_copyright(text, root)
        # The copyright header and the attribute denominator are read from the
        # raw text, since both live in places stripping would blank.
        for line, cname, name, fw, tag in scan(strip_comments(text)):
            if commented_attribute_above(text, line) or \
                    decision_prose_in_body(text, line):
                disabled += 1
                continue
            if foreign:
                tag += f' [check: header says "{foreign}", possibly vendored]'
            print(f'{path.relative_to(root)}:{line}: {cname}.{name} has '
                  f'assertions, no attribute and no caller [{fw}]{tag}')
            found += 1
    note = f'; {disabled} suppressed as deliberately disabled' if disabled else ''
    print(f'-- {found} uncollected .NET test(s) from {seen} .cs file(s), '
          f'{attributed} of them carrying a test attribute{note}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
