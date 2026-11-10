#!/usr/bin/env python3
"""Find Kotlin test functions JUnit cannot collect.

The Java check's failure mode, in Kotlin: under JUnit 4, JUnit 5 or kotlin.test
a function needs `@Test` to run, and one without it compiles, looks like a
test, and never runs.

A function is reported only when all of these hold:

  * the file imports a JUnit 4/5 or kotlin.test annotation, and does not use
    Kotest or Spek, which collect specs without annotations, or TestNG, whose
    class-level @Test makes every public method a test
  * the enclosing class is test-named, or is an `@Nested` inner class
  * the class does not extend JUnit 3's TestCase, which collects by name
  * the function is not private, not an override, not in a companion object,
    takes no arguments and returns Unit
  * it is named test* or uses a backtick name, the usual Kotlin test style
  * it carries no JUnit-shaped annotation, live or commented out
  * nothing in the tree calls it or takes a reference to it
"""
import argparse
import pathlib
import re
import sys

TEST_IMPORT = re.compile(
    r'^\s*import\s+(?:'
    r'org\.junit\.jupiter\.api\.'
    r'(?:Test|Nested|RepeatedTest|TestFactory|TestTemplate|BeforeEach|AfterEach'
    r'|BeforeAll|AfterAll|Disabled|\*)'
    r'|org\.junit\.(?:Test|Ignore|Before|After|BeforeClass|AfterClass|runner\.)'
    r'|kotlin\.test\.(?:Test|BeforeTest|AfterTest|Ignore|\*)'
    r')', re.M)

# These frameworks register tests without a per-function annotation.
OTHER_RUNNER = re.compile(r'^\s*import\s+(?:io\.kotest|org\.spekframework|org\.testng)\.', re.M)

EXTENDS_TESTCASE = re.compile(r':\s*(?:junit\.framework\.)?TestCase\s*\(')

# Same breadth as the Java check: over-matching costs a missed finding,
# under-matching costs a PR that calls a live test dead.
KNOWN_ANNOTATION = re.compile(
    r'@(?:[\w.]+\.)?(?:\w*Test\w*|\w*Template\w*'
    r'|BeforeEach|AfterEach|BeforeAll|AfterAll|Before|After|BeforeClass'
    r'|AfterClass|Disabled|Ignore|Nested|ArchTest|Property'
    r'|Benchmark|Setup|TearDown|Theory|Example|Provide)\b')

_ANN = r'@(?:[\w.]+\.)?(?:\w*Test\w*|Ignore|Disabled)\b'
COMMENTED_ANNOTATION = re.compile(r'^\s*(?://+|\*)\s*' + _ANN)

CLASS_DECL = re.compile(
    r'^[ \t]*((?:@[\w.]+(?:\([^)\n]*\))?[ \t]+)*)'
    r'((?:(?:public|internal|private|protected|open|abstract|final|inner|data'
    r'|sealed|enum)[ \t]+)*)'
    r'(class|interface|object)[ \t]+(\w+)([^{}]{0,400}?)\{', re.M)

COMPANION = re.compile(r'\bcompanion\s+object\b[^{}]{0,200}?\{')

METHOD_DECL = re.compile(
    r'^([ \t]*)((?:@[\w.]+(?:\([^)\n]*\))?[ \t]+)*)'
    r'((?:(?:public|internal|protected|private|open|override|suspend|final)[ \t]+)*)'
    r'fun[ \t]+(test\w*|`[^`\n]+`)[ \t]*\(([^)]*)\)'
    r'[ \t]*(?::[ \t]*([\w.<>?]+))?[ \t]*(\{|=[ \t]*\w+)', re.M)

TEST_CLASS_NAME = re.compile(r'(?:Test|Tests|TestCase|IT|ITCase)$')

SKIP_PARTS = ('build', 'target', 'out', '.git', '.gradle', '_vendor', 'vendored',
              'externals', 'third_party', 'thirdparty', 'bundled', 'patched')


def blank_comments(text):
    """Blank comments and string bodies, keeping every offset and newline.

    Kotlin adds raw strings: a `\"\"\"` literal can hold quotes and code-shaped
    text, so it is skipped to its closing triple quote, not the next quote.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        if text.startswith('//', i):
            j = text.find('\n', i)
            j = n if j < 0 else j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
        elif text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] not in '"\n':
                if text[j] == '\\':
                    j += 1
                j += 1
            j = min(j + 1, n)
        elif text[i] == "'" and i + 2 < n and (text[i + 2] == "'" or text[i + 1] == '\\'):
            j = text.find("'", i + 2) + 1 or n
        else:
            i += 1
            continue
        for k in range(i, j):
            if out[k] != '\n':
                out[k] = ' '
        i = j
    return ''.join(out)


def annotations_above(text, start):
    """The annotation block above `start`, and whether one was commented out.

    Tracks bracket depth so multi-line annotation arguments are consumed, the
    same walk the Java check uses.
    """
    lines = text[:start].split('\n')[:-1]
    depth = 0
    found = []
    commented = False
    for line in reversed(lines):
        s = line.strip()
        closers = s.count(')') + s.count('}') + s.count(']')
        openers = s.count('(') + s.count('{') + s.count('[')
        if depth > 0:
            found.append(s)
            depth += closers - openers
            continue
        if not s:
            continue
        if s.startswith(('//', '/*', '*', '*/')):
            if COMMENTED_ANNOTATION.match(s):
                commented = True
            continue
        if s in ('}', '{'):
            break
        if s.startswith('@') or closers > openers:
            found.append(s)
            depth += closers - openers
            continue
        break
    names = '\n'.join(m.group(0) for m in re.finditer(r'@[\w.]+', '\n'.join(found)))
    return names, commented


def body_end(text, open_brace):
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def class_spans(code):
    """(name, start, end, header, nested) for every class, interface or object."""
    for m in CLASS_DECL.finditer(code):
        open_brace = m.end() - 1
        above, _ = annotations_above(code, m.start())
        nested = '@Nested' in (m.group(1) + above)
        yield m.group(4), open_brace, body_end(code, open_brace), m.group(5), nested


def innermost(spans, pos):
    best = None
    for span in spans:
        if span[1] < pos < span[2] and (best is None or span[1] > best[1]):
            best = span
    return best


def scan(path):
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    if not TEST_IMPORT.search(text) or OTHER_RUNNER.search(text):
        return []
    code = blank_comments(text)
    spans = list(class_spans(code))
    companions = [(m.end() - 1, body_end(code, m.end() - 1)) for m in COMPANION.finditer(code)]
    hits = []
    for m in METHOD_DECL.finditer(code):
        pos = m.start(4)
        owner = innermost(spans, pos)
        if owner is None:
            continue
        name, _, _, header, nested = owner
        if not (TEST_CLASS_NAME.search(name) or nested):
            continue
        if EXTENDS_TESTCASE.search(header):
            continue
        if any(s < pos < e for s, e in companions):
            continue
        mods = m.group(3).split()
        if 'private' in mods or 'override' in mods:
            continue
        if m.group(5).strip():
            continue
        if m.group(6) and m.group(6) != 'Unit':
            continue
        # An expression body is a test only when it runs a test scope, like
        # `= runTest { }`; `= 3` is a helper returning a value.
        if m.group(7).startswith('=') and not re.match(r'=\s*run\w*', m.group(7)):
            continue
        above, crossed_out = annotations_above(text, m.start())
        if crossed_out:
            continue
        if KNOWN_ANNOTATION.search(m.group(2) + '\n' + above):
            continue
        hits.append((code[:pos].count('\n') + 1, name, m.group(4)))
    return hits


def tree_callers(roots, names):
    """For each name, calls and references across .kt and .java minus declarations."""
    if not names:
        return {}
    use = {n: re.compile(r'(?<![\w`])' + re.escape(n) + r'(?![\w`])\s*\(|::' + re.escape(n) + r'(?![\w`])')
           for n in names}
    decl = {n: re.compile(r'\bfun\s+' + re.escape(n) + r'\s*\(') for n in names}
    mentions = {n: 0 for n in names}
    decls = {n: 0 for n in names}
    for root in roots:
        for ext in ('*.kt', '*.java'):
            for path in pathlib.Path(root).rglob(ext):
                if any(p in SKIP_PARTS for p in path.parts):
                    continue
                try:
                    text = path.read_text(encoding='utf-8', errors='replace')
                except OSError:
                    continue
                code = blank_comments(text) if ext == '*.kt' else text
                for n in names:
                    if n in code:
                        mentions[n] += len(use[n].findall(code))
                        decls[n] += len(decl[n].findall(code))
    return {n: mentions[n] - max(decls[n], 1) for n in names}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roots', nargs='+')
    args = ap.parse_args()
    files = 0
    candidates = []
    for root in args.roots:
        for path in pathlib.Path(root).rglob('*.kt'):
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
    print(f'-- {total} candidate(s) from {files} Kotlin file(s) in {len(args.roots)} '
          f'root(s); {len(candidates) - total} dropped as called elsewhere in the tree',
          file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
