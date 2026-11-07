#!/usr/bin/env python3
"""Find test methods JUnit 5 cannot collect.

JUnit 3 collected any `public void testFoo()` in a TestCase subclass. JUnit 4
and 5 require an annotation. So a 3-to-5 migration can leave a `testFoo()`
behind that still compiles, still looks like a test, and never runs again.

A method is reported only when all of these hold, which is what keeps the
false-positive rate low enough to act on:

  * the file imports org.junit.jupiter, so annotations are mandatory here
  * the class does not extend TestCase, which would collect by name
  * the method is public/protected void, takes no required arguments and is
    named test*
  * it carries no JUnit annotation and no @Override
  * nothing in the WHOLE TREE calls it, so it is not a helper that merely
    shares the prefix. The check used to be file-local, and keycloak's
    AbstractMigrationTest reported 35 methods from one file: protected template
    methods in an abstract class that only subclasses call, from other files.
    A caller in another file is still a caller.
"""
import argparse
import pathlib
import re
import sys

# An ANNOTATION import, not merely anything under org.junit.jupiter. A static
# import of `Assertions.assertThrows` is framework-agnostic: openapi-generator's
# CodeGenMojoTest imports exactly that while being a JUnit 3 class, and keying on
# the package reported all 27 of its live, name-collected methods as dead.
JUNIT5_IMPORT = re.compile(
    r'^\s*import\s+(?:'
    r'org\.junit\.jupiter\.api\.'
    r'(?:Test|Nested|RepeatedTest|TestFactory|TestTemplate|ParameterizedTest'
    r'|BeforeEach|AfterEach|BeforeAll|AfterAll|Disabled|\*)'
    # JUnit 4 requires @Test just as much as 5 does, so the seam is identical
    # there. Scoping this to jupiter suppressed keycloak's
    # LDAPSearchForUsersPaginationTest, a JUnit 4 class carrying 16 @Test
    # annotations and one method without.
    r'|org\.junit\.(?:Test|Ignore|Before|After|BeforeClass|AfterClass|runner\.)'
    r')', re.M)

# JUnit 3 collects `public void testFoo()` by NAME, so a class in that world has
# nothing missing. The base is often reached through a chain: openapi-generator's
# CodeGenMojoTest extends BaseTestCase extends Maven's AbstractMojoTestCase
# extends junit.framework.TestCase. Named third-party harnesses are listed
# because their own source is not in the tree to follow.
EXTENDS_TESTCASE = re.compile(
    r'\bextends\s+(?:junit\.framework\.)?(?:TestCase'
    r'|AbstractMojoTestCase|AbstractMojoTestCase<[^>]*>'
    r'|PlexusTestCase|TestSetup)\b')

# Any of these means JUnit already knows about the method, or a parent class does.
# The optional dotted prefix matters: junit-framework's own LauncherFactoryTests
# writes `@org.junit.Test` in full, and a bare `@Test` pattern reads that as
# unannotated.
#
# `\w*Test\w*` rather than a list of names, because third-party extensions ship
# their own `@TestTemplate`-based annotations and an unlisted one reads as
# unannotated. netty's EpollSocketChannelConfigTest carries
# `@RepeatedIfExceptionsTest(repeats = 4)` from io.github.artsok, and an earlier
# version of this pattern reported both of its methods as dead when they run.
# The breadth is deliberate: over-matching here costs a missed finding, while
# under-matching costs a PR that claims a live test is dead.
# A project can define its own registering annotation, and the name does not
# have to contain "Test": Apache Kafka drives parameterised integration tests
# with `@ClusterTemplate("withRemoteStorage")`, which left four of its methods
# reported as uncollected when they are the opposite, run once per template.
# So `\w*Template\w*` joins `\w*Test\w*` as a name shape to trust.
KNOWN_ANNOTATION = re.compile(
    r'@(?:[\w.]+\.)?(?:\w*Test\w*|\w*Template\w*'
    r'|BeforeEach|AfterEach|BeforeAll|AfterAll|Before|After|BeforeClass'
    r'|AfterClass|Disabled|Ignore|Override|Nested|ArchTest|Property'
    r'|Benchmark|Setup|TearDown|Theory|Example|Provide|RepeatedTest'
    r'|ParameterizedClass|TestFactory)\b')

# No annotation prefix here: annotations are read separately, and a
# `(?:@\w+[^\n]*\n)*` prefix backtracks catastrophically on large files. The
# first version of this tool spent over fifteen minutes on one repo for that
# reason and had to be killed.
CLASS_DECL = re.compile(
    r'^[ \t]*(?:(?:public|final|abstract|static|sealed)[ \t]+)*'
    r'(?:class|interface|enum)[ \t]+(\w+)([^{;]{0,400}?)\{', re.M)

METHOD_DECL = re.compile(
    r'^([ \t]*)(?:(?:public|protected)\s+)'
    r'(?:static\s+|final\s+|synchronized\s+)*'
    r'void\s+(test\w*)\s*\(([^)]*)\)', re.M)

TEST_CLASS_NAME = re.compile(r'(?:Test|Tests|TestCase|IT|ITCase)$')

# A commented-out annotation is a decision, not an omission. Apache dubbo's
# EnableDubboConfigTest reads `// @Test` above both of its methods and the file
# carries ZERO live @Test annotations, so the whole class was switched off on
# purpose. Same rule as the .NET scanner: the annotation sits at one END of the
# comment with any remark at the other, because prose ABOUT an annotation has
# words on both sides.
_ANN = r'@(?:[\w.]+\.)?(?:Test|ParameterizedTest|RepeatedTest|TestFactory'
_ANN += r'|TestTemplate|Disabled|Ignore)\b(?:\([^)]{0,120}\))?'
COMMENTED_ANNOTATION = re.compile(
    r'^\s*(?://+|\*)\s*(?:'
    r'.{0,80}?' + _ANN + r'\s*$'
    r'|' + _ANN + r'[^@]{0,60}$'
    r')')


_TESTCASE_BASES = {}


# See find-shadowed-tests.py: a vendored tree is excluded because the project
# has written it off, not because the analysis fails there.
SKIP_PARTS = ('build', 'target', 'out', '.git', '_vendor', 'vendored',
              'externals', 'third_party', 'thirdparty', 'bundled', 'patched')


def junit3_bases(roots):
    """Names of in-tree classes whose `extends` chain reaches a JUnit 3 TestCase.

    Resolved by repeated passes over a name-to-parent map rather than by parsing
    imports, which is enough because the chain is almost always inside the tree
    and the leaf harness is covered by EXTENDS_TESTCASE's named list.
    """
    key = tuple(str(r) for r in roots)
    if key in _TESTCASE_BASES:
        return _TESTCASE_BASES[key]
    parent = {}
    for root in roots:
        for path in pathlib.Path(root).rglob('*.java'):
            if any(p in SKIP_PARTS for p in path.parts):
                continue
            try:
                txt = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for m in re.finditer(r'\bclass\s+(\w+)[^{;]{0,200}?\bextends\s+([\w.]+)', txt):
                parent[m.group(1)] = m.group(2).split('.')[-1]
    known = set()
    for _ in range(8):
        grew = False
        for child, par in parent.items():
            if child in known:
                continue
            if EXTENDS_TESTCASE.search('extends ' + par) or par in known:
                known.add(child)
                grew = True
        if not grew:
            break
    _TESTCASE_BASES[key] = known
    return known


def blank_comments(text):
    """Blank comment bodies, keeping every byte offset and newline.

    Commented-out CODE looks exactly like code. Apache dubbo's TelnetCodecTest
    wraps a whole method in `/*@Test ... */`, and the declaration pattern read
    it as a live method with a crossed-out annotation above it. Offsets are
    preserved so line numbers and the upward annotation walk still line up, and
    the walk is given the RAW text so it can still see `// @Test`.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == '//':
            j = text.find('\n', i)
            j = n if j < 0 else j
        elif two == '/*':
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            i = min(j + 1, n)
            continue
        else:
            i += 1
            continue
        for k in range(i, j):
            if out[k] != '\n':
                out[k] = ' '
        i = j
    return ''.join(out)


def annotations_above(text, start):
    """Collect the annotation block directly above `start`.

    Walks up line by line, but tracks bracket depth, because an annotation's
    ARGUMENTS can contain anything. Two shapes from Apache Kafka defeated
    simpler versions of this:

        @ClusterTest(                      <- a plain line-walk stops at the
            brokerSecurityProtocol = ...      lone `)` and never sees this
        )

        @ClusterTests({                    <- a "scan back to the last brace"
            @ClusterTest(serverProperties = {  version lands INSIDE the args,
                @ClusterConfigProperty(...)    because they contain braces
            })
        })

    Together those produced 73 and then 82 false hits in kafka, every one an
    annotated test. So: a line is consumed unconditionally while we are still
    inside an unclosed argument list, and the ordinary stop rules apply only at
    depth zero.
    """
    lines = text[:start].split('\n')[:-1]
    depth = 0          # unmatched closers seen so far, walking upward
    found = []
    commented = False
    for line in reversed(lines):
        s_line = line.strip()
        closers = line.count(')') + line.count('}') + line.count(']')
        openers = line.count('(') + line.count('{') + line.count('[')
        if depth > 0:
            # Inside an annotation's arguments: take the line and keep going.
            found.append(s_line)
            depth += closers - openers
            continue
        if not s_line:
            continue
        if s_line.startswith(('//', '/*', '*', '*/')):
            if COMMENTED_ANNOTATION.match(s_line):
                commented = True
            continue
        # A LONE `}` is the previous member's body closing, which is the
        # boundary. `)` or `})` is an annotation's argument list, which is not.
        # Without this split, the walk treats the previous method's closing
        # brace as an open argument list and sails up into ITS annotation,
        # which suppressed every genuine hit.
        if s_line in ('}', '};', '{'):
            break
        if s_line.startswith('@') or closers > openers:
            found.append(s_line)
            depth += closers - openers
            continue
        break
    block = '\n'.join(reversed(found))
    # Only the annotation NAMES, so argument text cannot be mistaken for one.
    names = '\n'.join(m.group(0) for m in re.finditer(r'@[\w.]+', block))
    return names, commented


def class_spans(text):
    """Yield (name, body_start, body_end, header) for every class in the file."""
    for m in CLASS_DECL.finditer(text):
        open_brace = m.end() - 1
        depth = 0
        for i in range(open_brace, len(text)):
            c = text[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    yield m.group(1), open_brace, i, m.group(2)
                    break


def takes_no_required_args(params):
    """JUnit can still run a method that only asks for injected parameters."""
    p = params.strip()
    if not p:
        return True
    injectable = ('TestInfo', 'TestReporter', 'RepetitionInfo', 'TempDir')
    return all(any(t in part for t in injectable) for part in p.split(','))


def innermost_class(spans, pos):
    """The tightest class whose body contains `pos`.

    A method has to be judged against the class that actually declares it, not
    any class that merely encloses it. junit-framework declares a nested
    `JUnit4Example` fixture inside `LauncherFactoryTests`; its method belongs to
    the fixture, which JUnit collects separately, so crediting it to the outer
    `*Tests` class reports a method that is not dead at all.
    """
    best = None
    for span in spans:
        _, start, end, _ = span
        if start < pos < end:
            if best is None or start > best[1]:
                best = span
    return best


JUNIT3_IN_TREE = set()


def scan(path):
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    if not JUNIT5_IMPORT.search(text):
        return []

    # Declarations are matched against the comment-blanked copy so that
    # commented-out code is not read as code; the annotation walk still gets
    # the raw text, because it has to be able to see `// @Test`.
    code = blank_comments(text)
    spans = list(class_spans(code))
    hits = []
    for m in METHOD_DECL.finditer(code):
        owner = innermost_class(spans, m.start())
        if owner is None:
            continue
        name, _, _, header = owner
        if not TEST_CLASS_NAME.search(name):
            continue
        if EXTENDS_TESTCASE.search(header):
            continue
        m_ext = re.search(r'\bextends\s+([\w.]+)', header)
        if m_ext and m_ext.group(1).split('.')[-1] in JUNIT3_IN_TREE:
            continue
        method = m.group(2)
        if not takes_no_required_args(m.group(3)):
            continue
        above, crossed_out = annotations_above(text, m.start())
        if crossed_out:
            continue
        if KNOWN_ANNOTATION.search(above):
            continue
        # A helper is called; a dead test is not. The file-local count is
        # kept as a cheap first filter; the tree-wide one runs afterwards, in
        # main, over just the names that survive this.
        refs = len(re.findall(r'\b' + re.escape(method) + r'\s*\(', text))
        if refs > 1:
            continue
        hits.append((text[:m.start()].count('\n') + 1, name, method))
    return hits


def tree_callers(roots, names):
    """For each name, mentions across every .java file minus its declarations.

    Two passes rather than one index: candidates are few, so grepping the tree
    for only their names is far cheaper than counting every identifier.

    Subtracting the DECLARATION count rather than a flat 1 is the same lesson
    the Go scanner learned. A name can be declared more than once across a
    tree, as keycloak declares testMigrationTo2_0_0 in both its current
    tests/base tree and its legacy testsuite/integration-arquillian one, and a
    second declaration is not a caller.
    """
    if not names:
        return {}
    call = {n: re.compile(r'\b' + re.escape(n) + r'\s*\(') for n in names}
    # A declaration is followed by a BODY; a call ends in a semicolon. Keying
    # on modifiers and a return type instead matched the call site too, because
    # the leading indentation satisfied both the modifier and the type group, so
    # declarations and mentions cancelled out and nothing was ever dropped.
    # `[^;()]*` for the parameter list keeps a lambda argument, `f(() -> {})`,
    # from reading as a declaration.
    decl = {n: re.compile(re.escape(n) + r'\s*\([^;()]*\)\s*'
                          r'(?:throws[^{;]*)?\{') for n in names}
    mentions = {n: 0 for n in names}
    decls = {n: 0 for n in names}
    for root in roots:
        for path in pathlib.Path(root).rglob('*.java'):
            if any(p in SKIP_PARTS for p in path.parts):
                continue
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for n in names:
                if n not in text:
                    continue
                mentions[n] += len(call[n].findall(text))
                decls[n] += len(decl[n].findall(text))
    return {n: mentions[n] - max(decls[n], 1) for n in names}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roots', nargs='+')
    args = ap.parse_args()

    global JUNIT3_IN_TREE
    JUNIT3_IN_TREE = junit3_bases(args.roots)

    files = 0
    candidates = []
    for root in args.roots:
        for path in pathlib.Path(root).rglob('*.java'):
            if not TEST_CLASS_NAME.search(path.stem):
                continue
            if any(p in SKIP_PARTS for p in path.parts):
                continue
            files += 1
            for line, cls, method in scan(path):
                candidates.append((path, line, cls, method))

    extra = tree_callers(args.roots, {c[3] for c in candidates})
    total = 0
    for path, line, cls, method in candidates:
        if extra.get(method, 0) > 0:
            continue
        print(f'{path}:{line}  {cls}.{method}()')
        total += 1
    suppressed = len(candidates) - total
    print(f'-- {total} candidate(s) from {files} test file(s) '
          f'in {len(args.roots)} root(s); {suppressed} dropped as '
          f'called elsewhere in the tree', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
