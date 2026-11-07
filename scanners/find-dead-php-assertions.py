#!/usr/bin/env python3
"""Find PHPUnit assertions that can never run because an earlier call threw.

The seam is the PHP twin of `find-dead-assertions.py`: once a test calls
`$this->expectException(...)`, the statement that actually throws ends the
method, so anything after it is dead. Reports candidates only; every hit still
has to be read, because the same shapes have honest uses:

  1. The assertion IS the raiser (it calls the throwing code itself).
  2. The throwing call sits inside a try/catch, so control continues.
  3. The method returns or the throwing call is the last statement (nothing dead).
  4. expectException is set up for a LATER call and the assertions in between
     genuinely run.
  5. expectException is CONDITIONAL, the shape data-provider tests use:
     `if (null !== $expectedExceptionMessage) { $this->expectException(...); }`.
     The provider feeds both throwing and non-throwing rows, so the trailing
     assertion is live for every row that does not throw. Filtered out below,
     because it accounted for every false positive in api-platform and composer.

Discriminating rule, same as the Python scanner: an assertion about the
exception object is dead for sure; one about a result or a mock may be an
intentional guard for the did-not-throw path.

  6. `expectDeprecation()` is NOT in the trigger list, because it does not abort.
     PHP-CS-Fixer's `FutureTest::testTriggerDeprecationWhenFutureModeIsOff`
     triggers a deprecation and then asserts on the collected list, and mutating
     that assertion fails the test, so it plainly runs. Deprecation and warning
     expectations are generally verified at the end of the test rather than at
     the point of the call.
"""
import re
import sys
from pathlib import Path

EXPECT = re.compile(r'\$this->expect(Exception|ExceptionMessage|ExceptionMessageMatches|ExceptionCode|Error|Warning)\s*\(')

# A test class can define its OWN expectError()/expectException() taking a
# callable, which is CLOSURE-SCOPED and the opposite of PHPUnit's method-wide
# version: it catches inside the callback and returns, so everything after it
# still runs. craftcms/cms does exactly this in SiteScopedMutationsTest:
#
#     private function expectError(callable $callback): void {
#         try { $callback(); }
#         catch (Error $e) { self::assertSame('Unable to...', $e->getMessage()); return; }
#         self::fail('The mutation was not refused.');
#     }
#
# Matching the NAME and assuming PHPUnit semantics reported 4 dead assertions in
# a file where all four are live. Two independent tells, either of which is
# enough to disqualify the file:
#   - the class declares its own expect* method, shadowing PHPUnit's
#   - the expectation is called WITH a closure argument: expectError(fn() => ..)
LOCAL_EXPECT_DEF = re.compile(
    r'(?:private|protected|public)\s+function\s+expect(?:Error|Exception|Warning)\s*\(\s*callable')
EXPECT_WITH_CLOSURE = re.compile(
    r'expect(?:Exception|Error|Warning)\s*\(\s*(?:fn\s*\(|function\s*\(|\[|\$\w+\s*\))')
ASSERT = re.compile(r'^\s*(\$this->|self::|static::)(assert|expectNotToPerformAssertions)')
METHOD = re.compile(r'^\s*(?:public|protected|private)?\s*function\s+(\w+)\s*\(')


# Parens inside a string literal must not move the depth. Carbon's
# expectExceptionMessage() carries "(in particular if you are unserializing)"
# across three concatenated literals, and counting those parens desynced the
# statement joiner so the dead assertion after it was never reported.
STRLIT = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")


def paren_delta(line: str) -> int:
    bare = STRLIT.sub("''", line)
    return bare.count("(") - bare.count(")")


def php_test_files(root):
    """Every PHPUnit test file, under BOTH naming conventions.

    phpbb/phpbb has 391 `*_test.php` files and zero `*Test.php`, so a
    `*Test.php` glob reported "0 test files" for a project with 5,265 merged
    PRs. Older PHP codebases use the snake_case form, and PHPUnit itself only
    cares about the `suffix`/`defaultTestSuffix` config, not the case.
    """
    seen = set()
    for pat in ('*Test.php', '*_test.php', 'test_*.php'):
        for f in Path(root).rglob(pat):
            if f not in seen:
                seen.add(f)
                yield f

HITS = 0
# Counted so the suppression is visible rather than silent.
SUBJECTS = 0


def scan(path: Path):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    # A class that defines its own callable-taking expect*() shadows PHPUnit's
    # method-wide version with a closure-scoped one, so nothing in this file can
    # be judged by PHPUnit semantics. craftcms/cms cost 4 false positives here.
    if LOCAL_EXPECT_DEF.search("\n".join(lines)):
        return
    i, n = 0, len(lines)
    while i < n:
        m = METHOD.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        # Collect the method body by brace depth, starting at the opening brace.
        depth, j, body, started = 0, i, [], False
        while j < n:
            depth += lines[j].count("{") - lines[j].count("}")
            body.append((j + 1, lines[j]))
            if "{" in lines[j]:
                started = True
            if started and depth <= 0:
                break
            j += 1
        text = "\n".join(l for _, l in body)
        conditional_expect = any(
            EXPECT.search(l) and any(
                prev.strip().startswith(("if ", "if(")) for prev in
                [l2 for _, l2 in body[max(0, k - 3):k]]
            )
            for k, (_, l) in enumerate(body)
        )
        # Only an assertion can raise PHPUnit's own AssertionFailedError, so a
        # test expecting one is testing an assertion helper and the trailing
        # assertion IS the raiser, not dead code after it. That is 17 of
        # cakephp's 34 candidates and every one of EasyAdminBundle's, both of
        # which test their own assertion traits:
        #   expectException(AssertionFailedError::class);
        #   expectExceptionMessage("Failed asserting that 'x' cookie is not set");
        #   $this->post('/posts/index');          <- harmless, not the thrower
        #   $this->assertCookieNotSet('x');       <- the subject
        # The intervening call is why the "nothing in between" rule misses these.
        expects_assertion_failure = re.search(
            r'expectException\(\s*\\?[\w\\]*'
            r'(?:AssertionFailedError|ExpectationFailedException)', text)
        if expects_assertion_failure:
            i = j + 1
            continue

        if (
            "expect" in text and EXPECT.search(text)
            and "try {" not in text and "catch" not in text
            and not conditional_expect
            and not EXPECT_WITH_CLOSURE.search(text)
        ):
            # An assertion is dead only if it comes AFTER the last non-assertion
            # statement, because that last statement is the one that throws and
            # ends the method. A test that sets expectException up top and puts
            # the throwing call last is correct, and this rule leaves it alone.
            # Statements are joined by PAREN depth, not taken line by line.
            # A wrapped call
            #     self::assertEquals(
            #         Command::FAILURE,
            #         $appTester->run(...)
            #     );
            # otherwise contributes its continuation lines as separate
            # non-assertion statements, which pushes `last_call` past the real
            # assertion and hides it. That was 2 of composer's 6.
            seen_expect = False
            depth_here = 0
            stmts = []  # (lineno, text, is_assertion) at the method's own level
            pend_line, pend_parts, pend_depth = None, [], 0
            expect_depth = 0
            for lineno, line in body:
                opens, closes = line.count("{"), line.count("}")
                at_top = depth_here <= 1
                stripped = line.strip()
                if expect_depth > 0:
                    # Still inside a wrapped expectException*() call.
                    expect_depth += paren_delta(line)
                elif (pend_line is None and EXPECT.search(line)
                      and not stripped.startswith(("//", "*", "/*", "#"))):
                    # A COMMENTED-OUT expectException means the opposite: the author
                    # switched it off, so the assertions after it DO run. LycheeOrg/Lychee
                    # testBadZipExtract has `// $this->expectException(ZipInvalidException::class);`
                    # and a live assertStatus below it, which this read as dead. Removing that
                    # assertion would have been the worst kind of bad PR.
                    seen_expect = True
                    expect_depth = max(0, paren_delta(line))
                elif pend_line is not None or (
                    seen_expect and at_top and stripped
                    and not stripped.startswith(("//", "*", "/*", "}"))
                ):
                    # Once a statement is pending, its continuation lines belong
                    # to it whatever the BRACE depth. Carbon writes
                    # `Exception::allow(static function () use ($p) {` ... `});`
                    # and the closing `});` sits one brace deeper, so gating
                    # continuations on at_top left the statement open forever
                    # and swallowed the dead assertion after it.
                    if pend_line is None:
                        pend_line, pend_parts, pend_depth = lineno, [], 0
                    if stripped:
                        pend_parts.append(stripped)
                    pend_depth += paren_delta(line)
                    if pend_depth <= 0 and stripped.endswith((";", "{", "}")):
                        joined = " ".join(pend_parts)
                        stmts.append((pend_line, joined, bool(ASSERT.match(pend_parts[0]))))
                        pend_line, pend_parts, pend_depth = None, [], 0
                depth_here += opens - closes
            if pend_parts:
                stmts.append((pend_line, " ".join(pend_parts), bool(ASSERT.match(pend_parts[0]))))
            last_call = max((k for k, (_, _, a) in enumerate(stmts) if not a), default=-1)
            # With NO non-assertion statement after expectException, the first
            # assertion is itself the raiser, so only the ones after it are
            # dead. This is documented case 1 above, and it was every hit in
            # EasyAdminBundle, whose tests check that its own assertion helpers
            # raise: `expectException(AssertionFailedError); assertIndexFullEntityCount(-1);`
            # has nothing between the two, so the assertion is the subject.
            start = last_call + 1 if last_call >= 0 else 1
            for lineno, stripped, is_assert in stmts[start:]:
                if is_assert:
                    # An assertion helper can be the RAISER when the test is
                    # about that helper's own argument validation, and then a
                    # non-assertion statement before it does not make it dead.
                    # api-platform's testAssertJsonContainsWithJsonScalarString
                    # expects InvalidArgumentException from assertJsonContains
                    # itself, with `self::createClient()->request(...)` in
                    # between, so the existing "nothing before it" suppression
                    # did not apply. The test NAME carrying the method's own
                    # name is the signal that the assertion is the subject.
                    m = re.search(r'\$this->(assert\w+)|self::(assert\w+)', stripped)
                    called = (m.group(1) or m.group(2)) if m else ''
                    if called and called.lower() in name.lower():
                        global SUBJECTS
                        SUBJECTS += 1
                        continue
                    global HITS
                    HITS += 1
                    print(f"{path}:{lineno}: {name}: {stripped}")
        i = j + 1

roots = sys.argv[1:] or ["."]
# A denominator, because this tool printed nothing at all when it found
# nothing, so "no dead assertions" and "scanned no files" were the same
# output. Sylius, Twig and Tatoeba were each recorded as 0 on that basis.
examined = 0
for root in roots:
    for p in php_test_files(root):
        if "/vendor/" in str(p):
            continue
        examined += 1
        scan(p)
note = f"; {SUBJECTS} suppressed as the assertion under test" if SUBJECTS else ""
print(f"-- {HITS} dead assertion(s) from {examined} php test file(s){note}",
      file=sys.stderr)
