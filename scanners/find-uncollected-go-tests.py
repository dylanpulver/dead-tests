#!/usr/bin/env python3
"""Find Go test functions the toolchain never runs.

`go test` collects a function only when it is named `TestXxx` with an exported
first letter AND lives in a `_test.go` file. Two mistakes slip past both the
compiler and the linters, because Go only rejects unused *variables* and
*imports*, never an unused function:

  lowercase   `func testFoo(t *testing.T)` in a _test.go file. Takes
              *testing.T, so it was written as a test, but the lower-case name
              hides it from the runner. Reported only when nothing calls it,
              which is what separates it from a deliberate shared helper.

  misplaced   `func TestFoo(t *testing.T)` in a file NOT ending in _test.go.
              Never compiled into the test binary at all.

Both stay green forever, exactly like the JUnit and PHPUnit versions of this
seam.
"""
import argparse
import pathlib
import re
import sys

# A *testing.T / *testing.B / *testing.F parameter is what marks the intent.
TEST_PARAM = r'\*testing\.[TBF]\b'
LOWER_TEST = re.compile(
    r'^func\s+(test[A-Za-z0-9_]*)\s*\(\s*\w+\s+' + TEST_PARAM, re.M)
EXPORTED_TEST = re.compile(
    r'^func\s+(Test[A-Za-z0-9_]*)\s*\(\s*\w+\s+' + TEST_PARAM, re.M)

SKIP_DIRS = {'vendor', 'testdata', '.git', 'third_party'}


def strip_comments(text):
    """Blank out comment bodies, keeping every byte offset and newline.

    A doc comment is allowed to SHOW a function declaration. rclone's
    fstest/run.go opens with a package comment demonstrating usage:

        /*
        func TestMkdir(t *testing.T) {
            r := fstest.NewRun(t)
        ...
        */

    which the exported-test pattern read as a real declaration outside a
    _test.go file, and reported as a stranded test. Offsets are preserved so
    reported line numbers still point at the real source.
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
        elif text[i] in '"`':
            # Skip over string literals so a '//' inside one is not treated as
            # a comment start; their contents cannot declare a function anyway.
            q = text[i]
            j = i + 1
            while j < n and text[j] != q:
                if q == '"' and text[j] == '\\':
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


_PKG_CACHE = {}


def package_text(path):
    """Every .go file in the same directory, concatenated.

    Go functions are package-scoped, so a lowercase helper declared in
    `a_test.go` is callable from `b_test.go` without any qualification. Counting
    references in one file only reports shared helpers as dead: prometheus's
    `testChunkSTHandling` lives in `st_helper_test.go` and is called from
    `chunk_test.go` beside it.
    """
    key = str(path.parent)
    if key not in _PKG_CACHE:
        buf = []
        for sibling in path.parent.glob('*.go'):
            try:
                buf.append(sibling.read_text(encoding='utf-8', errors='replace'))
            except OSError:
                pass
        _PKG_CACHE[key] = '\n'.join(buf)
    return _PKG_CACHE[key]


def calls(text, name):
    """References to `name` other than its own declaration.

    Counts a bare mention too, not just `name(`, because a test helper is as
    often handed to `t.Run(..., testParse)` as called directly.
    """
    return len(re.findall(r'\b' + re.escape(name) + r'\b', text)) - 1


def scan_file(path):
    try:
        text = strip_comments(path.read_text(encoding='utf-8', errors='replace'))
    except OSError:
        return []

    hits = []
    if path.name.endswith('_test.go'):
        pkg = package_text(path)
        for m in LOWER_TEST.finditer(text):
            name = m.group(1)
            if calls(pkg, name) > 0:
                continue          # a helper, shared on purpose
            line = text[:m.start()].count('\n') + 1
            hits.append((line, name, 'lowercase name, never collected'))
    elif path.suffix == '.go':
        # An exported TestXxx outside a _test.go file is usually a deliberate
        # shared helper that another package's tests call, as prometheus's
        # tsdbutil.TestDirLockerUsage is. Only an uncalled one is stranded, and
        # the whole repo has to be checked, not just this package.
        for m in EXPORTED_TEST.finditer(text):
            name = m.group(1)
            if repo_calls(name) > 0:
                continue
            line = text[:m.start()].count('\n') + 1
            hits.append((line, name, 'not in a _test.go file'))
    return hits


_REPO_TEXT = []


def repo_calls(name):
    """Mentions of `name` across the repo that are not its own declaration.

    Subtracting the DECLARATION COUNT rather than a flat 1 matters: one name can
    be declared more than once in a package when the copies sit under opposite
    build constraints. caddy declares TestFileCreationMode in both
    filewriter_test.go (//go:build !windows) and filewriter_test_windows.go
    (//go:build windows), so a flat -1 read the second declaration as a call and
    silently suppressed it. Only one of that file's two dead tests was reported.
    A second declaration is not a caller.
    """
    mentions = sum(len(re.findall(r'\b' + re.escape(name) + r'\b', t))
                   for t in _REPO_TEXT)
    decls = sum(len(re.findall(r'^func\s+' + re.escape(name) + r'\s*\(', t, re.M))
                for t in _REPO_TEXT)
    return mentions - max(decls, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roots', nargs='+')
    args = ap.parse_args()

    paths = []
    for root in args.roots:
        for path in pathlib.Path(root).rglob('*.go'):
            if SKIP_DIRS & set(path.parts):
                continue
            paths.append(path)
    for path in paths:
        try:
            _REPO_TEXT.append(path.read_text(encoding='utf-8', errors='replace'))
        except OSError:
            pass

    files = 0
    total = 0
    if True:
        for path in paths:
            files += 1
            for line, name, why in scan_file(path):
                print(f'{path}:{line}  {name}  [{why}]')
                total += 1
    print(f'-- {total} candidate(s) from {files} go file(s) '
          f'in {len(args.roots)} root(s)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
