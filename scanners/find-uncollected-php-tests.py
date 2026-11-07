#!/usr/bin/env python3
"""Find PHPUnit test methods that are never collected, so never run.

PHPUnit collects a method only when its name starts with `test`, or it carries
`@test` / `#[Test]`. A public method in a TestCase that asserts things but has
neither is silently dead: no error, no skip, no mention in the output. It is the
PHP counterpart of the shadowed-test seam, which cannot exist in PHP because a
duplicate method name there is a compile-time fatal.

The discriminator is whether anything calls it. A helper such as
`assertOrderTotals()` invoked from real tests is legitimate and must not be
reported, so a method is only a candidate when its name appears nowhere else in
the file. Known honest shapes that are filtered out:

  1. Lifecycle and framework hooks (setUp, tearDown, provide*, data providers,
     __construct, and anything PHPUnit or the bundle calls by convention).
  2. Methods carrying `@test`, `#[Test]`, `@dataProvider`, `#[DataProvider]`,
     or `@before` / `@after` style attributes.
  3. Abstract or interface declarations, which have no body to run.
  4. Methods referenced anywhere else in the file, including via
     `[$this, 'name']`, `'name'` in a provider list, or a parent call.

Reports candidates only. Every hit still has to be read: a method may be called
from a sibling class in the same suite, which this does not model.
"""
import re
import sys
from pathlib import Path

PUBLIC_METHOD = re.compile(
    r'^[ \t]*public(?:\s+static)?\s+function\s+(\w+)\s*\(', re.M)
# A *Test.php file often also defines stubs and custom matchers. Only methods
# inside the test class itself can be test methods: laravel's
# DatabaseMigrationRefreshCommandTest defines a matcher stub with a `match()`
# method that PHPUnit calls itself, which read as uncollected otherwise.
CLASS_DECL = re.compile(
    r'^[ \t]*(?:final\s+|abstract\s+)*class\s+(\w+)([^{]*)\{', re.M)
ASSERTION = re.compile(r'\$this->assert|self::assert|static::assert|\$this->expect')
# Attributes and annotations that make PHPUnit call a method itself.
HOOK_MARKERS = re.compile(
    # The attribute may be namespaced or aliased: lcobucci/jwt does
    # `use PHPUnit\Framework\Attributes as PHPUnit;` and writes `#[PHPUnit\Test]`,
    # which a literal `#[Test]` misses and which produced 168 false hits in a
    # 53-file suite. `\\\\?(?:\w+\\\\)*` allows any leading namespace.
    r'@test\b|#\[\s*\\?(?:\w+\\)*Test\b|@dataProvider|'
    r'#\[\s*\\?(?:\w+\\)*DataProvider|@before|@after|'
    r'#\[\s*\\?(?:\w+\\)*Before|#\[\s*\\?(?:\w+\\)*After|'
    r'@depends|#\[\s*\\?(?:\w+\\)*Depends|'
    # PHPUnit calls pre/post-condition hooks itself; its own end-to-end fixtures
    # under tests/.../_files use them and read as uncollected otherwise.
    r'@preCondition|@postCondition|#\[\s*PreCondition|#\[\s*PostCondition')
HOOK_NAMES = re.compile(
    r'^(setUp|tearDown|setUpBeforeClass|tearDownAfterClass|__construct|'
    r'__destruct|onNotSuccessfulTest|provide\w*|\w*Provider|\w*DataProvider|'
    r'getContainer|createClient|getBundles|registerBundles|configureRoutes|'
    r'configureContainer|getKernelClass|createKernel)$')


def test_class_spans(text):
    """Byte ranges of classes that PHPUnit would collect tests from."""
    spans = []
    for m in CLASS_DECL.finditer(text):
        name, header = m.group(1), m.group(2)
        if not (name.endswith('Test') or 'TestCase' in header):
            continue
        depth, i = 0, text.index('{', m.start())
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        spans.append((m.start(), i))
    return spans


# `new class(...) extends Query { public function andWhere(...) }` is a test
# double built inline, and its overrides live INSIDE the test class's braces, so
# a span-based scan reads them as test methods. cakephp's HasManyTest produced
# exactly that false positive.
ANON_CLASS = re.compile(r'\bnew\s+class\b')


def anon_class_spans(text):
    """Byte ranges of anonymous class bodies, which are never collected from."""
    spans = []
    for m in ANON_CLASS.finditer(text):
        brace = text.find('{', m.end())
        if brace == -1:
            continue
        depth, i = 0, brace
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        spans.append((brace, i))
    return spans


# A class whose setUp() unconditionally calls markTestSkipped runs none of its
# tests, so an unprefixed method there is not worth reporting: adding the prefix
# would collect it and then skip it. livewire parks a whole asset-directive
# class that way, with "holding off on this..." as the reason.
SETUP_SKIP = re.compile(
    r'function\s+setUp\s*\([^)]*\)[^{]*\{'      # setUp signature
    r'(?:[^{}]|\{[^{}]*\})*?'                   # its body, one nesting deep
    r'\$this->markTestSkipped\(',
    re.S)


def setup_always_skips(text, span):
    """True when the class in `span` skips every test from setUp()."""
    a, b = span
    body = text[a:b]
    m = SETUP_SKIP.search(body)
    if not m:
        return False
    # Only unconditional skips count; a guarded one still lets tests run.
    head = body[:m.start()]
    setup_at = head.rfind('function setUp')
    between = body[setup_at:m.end()] if setup_at != -1 else ''
    return not re.search(r'\b(if|elseif|else|switch|match)\b', between)


def method_bodies(text):
    """Yield (name, start, end) for each public method, by brace matching."""
    for m in PUBLIC_METHOD.finditer(text):
        name = m.group(1)
        brace = text.find('{', m.end())
        if brace == -1:
            continue                      # abstract or interface declaration
        semi = text.find(';', m.end())
        if semi != -1 and semi < brace:
            continue                      # abstract: `function f();`
        depth, i = 0, brace
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        yield name, m.start(), i


def docblock_before(text, start):
    """Only the attribute and docblock block directly above the method.

    A fixed-size lookback window is wrong: 600 characters reaches back over the
    previous method and picks up ITS `@test` or `#[Test]`, which silently
    suppressed every real hit when this was first written. So walk up line by
    line and stop at the first line that is neither blank, a docblock line, nor
    an attribute.
    """
    lines = text[:start].split('\n')
    kept = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped == '' or stripped.startswith(('/**', '*', '*/', '//', '#[')):
            kept.append(line)
            continue
        break
    return '\n'.join(reversed(kept))


def reference_map(root):
    """name -> set of php files mentioning it, for the cross-file helper check.

    An own-file count cannot distinguish a shared helper from an uncollected
    test, because the callers of a helper are in other files by definition.
    craftcms's `CommandTest::ensureSession()` is called only from siblings.
    """
    refs = {}
    for f in Path(root).rglob('*.php'):
        if f.parts and set(f.parts) & {'vendor', '_vendor', 'vendored',
                                        'externals', 'third_party', 'bundled'}:
            continue
        try:
            text = f.read_text(errors='replace')
        except OSError:
            continue
        for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', text):
            refs.setdefault(m.group(1), set()).add(f)
    return refs



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

def scan(path):
    hits = []
    examined = 0
    refs = reference_map(path)
    for f in sorted(php_test_files(path)):
        # `_files` and `fixtures` hold inputs for other tests, not tests themselves.
        # A `*Test.php` SUFFIX does not make a file a test. silverstripe ships
        # `src/Dev/FunctionalTest.php`, a production base class in namespace
        # SilverStripe\Dev whose `assertPartialHTMLMatchBySelector()` and
        # `assertExactHTMLMatchBySelector()` are documented public API, and both
        # were reported as uncollected tests. Require a test DIRECTORY in the
        # path, matched case-insensitively so api-platform's merged finding
        # under `src/GraphQl/Tests/` still qualifies.
        if not any(part.lower() in ('test', 'tests') for part in f.parts):
            continue
        if {'vendor', '_files', 'fixtures', 'Fixtures'} & set(f.parts):
            continue
        try:
            text = f.read_text(errors='replace')
        except OSError:
            continue
        examined += 1
        spans = [sp for sp in test_class_spans(text)
                 if not setup_always_skips(text, sp)]
        anon = anon_class_spans(text)
        for name, start, end in method_bodies(text):
            if not any(a <= start <= b for a, b in spans):
                continue
            if any(a <= start <= b for a, b in anon):
                continue

            if name.startswith('test') or HOOK_NAMES.match(name):
                continue
            # A parked test, named so on purpose. htmlpurifier uses this.
            # `notestFoo` is `test` with `no` typed in front of it, which is how
            # yii2 parks `SecurityTest::notestGenerateVectors()`, a vector
            # GENERATOR whose docblock says its output is for cross-version
            # compatibility checks. Deliberate, not an accident.
            if name.startswith(('notest', 'nottest', 'xtest',
                                'disabled_', 'disable_', 'skip_', 'skipped_',
                                'xtest', 'ignore_')):
                continue
            if HOOK_MARKERS.search(docblock_before(text, start)):
                continue
            body = text[start:end]
            if not ASSERTION.search(body):
                continue
            # Called from anywhere else in the file? Then it is a helper.
            others = len(re.findall(r'\b' + re.escape(name) + r'\b', text))
            if others > 1:
                continue
            # Or from any other file, which is where a shared helper's callers are.
            if len(refs.get(name, ())) - (1 if f in refs.get(name, ()) else 0) > 0:
                continue
            line = text[:start].count('\n') + 1
            hits.append(f'{f}:{line}: {name}()')
    return hits, examined


def main():
    roots = sys.argv[1:] or ['.']
    hits = []
    examined = 0
    for r in roots:
        found, seen = scan(r)
        hits.extend(found)
        examined += seen
    print('\n'.join(hits))
    print(f'-- {len(hits)} candidate(s) from {examined} *Test.php file(s)',
          file=sys.stderr)


if __name__ == '__main__':
    main()
