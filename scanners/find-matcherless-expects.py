#!/usr/bin/env python3
"""Find `expect(...)` calls that never reach a matcher.

In Jest and Vitest, `expect(value)` on its own is a no-op. It builds the
assertion object and throws it away, so the line looks like a check, the test
passes, and nothing is verified. Neither runner complains, and no linter
catches it by default.

This is the JavaScript shape of the dead-assertion seam: the test is collected
and green while asserting nothing.

Reported only when the statement genuinely ends after the closing paren, so a
chain broken across lines (`expect(x)\\n  .toBe(y)`) is not flagged.
"""
import argparse
import pathlib
import re
import sys

CALL = re.compile(r'(?<![\w.$])expect\s*\(')
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', 'coverage', '.next',
             'out', 'vendor', '.yarn', '.pnpm-store', 'fixtures', '__fixtures__'}
TEST_FILE = re.compile(r'\.(test|spec)\.[cm]?[jt]sx?$')
JS_SUFFIX = ('.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs')
# Plenty of projects keep tests in a directory with plain file names rather than
# a `.test.` suffix: immer uses `__tests__/`, chalk, execa and jsdom use `test/`.
# Matching on the suffix alone found 0 files in each of those and reported them
# clean, which is the worst failure mode a scanner has.
TEST_DIRS = {'test', 'tests', '__tests__', 'spec', '__spec__'}
# A bare `test.js` at the package root is the standard single-file AVA layout,
# used by most of sindresorhus's packages and by remark. Matching only a `.test.`
# suffix or a test DIRECTORY found 0 files in del, ora, p-map and remark and
# reported all four clean.
TEST_STEMS = {'test', 'tests', 'spec', 'specs'}


# A file that declares its own `expect` is not calling a matcher library, so a
# bare call there asserts nothing only if THAT function asserts nothing.
# terser's test/mocha/lhs-expressions.js:238 declares
# `var expect = function(input, expected) { ... assert.throws(...) }`, and all
# seven of its two-argument calls are correct. Destructuring (`const {expect} =
# require('chai')`) deliberately does not match: that is the real expect.
OWN_EXPECT = re.compile(
    r'(?:\bfunction\s+expect\s*\()|(?:\b(?:const|let|var)\s+expect\s*=)')


def defines_own_expect(text):
    return bool(OWN_EXPECT.search(text))


def is_test_file(path):
    if path.suffix not in JS_SUFFIX:
        return False
    # A linter or formatter stores the code under test as standalone INPUT files,
    # and `TEST_DIRS & path.parts` happily collects them. Every one of biome's 11
    # reported hits lived in `crates/*/tests/specs/`, including
    # `noMisplacedAssertion/invalid.js`, which is a fixture for a rule that
    # detects misplaced assertions. 11 of 11 false.
    #
    # Only the `tests/specs` pair is excluded. Measured across the 266-hit corpus
    # sweep: `tests/specs` accounted for 10 lines, all in biome, while
    # `fixtures`, `__fixtures__`, `snapshots` and `__snapshots__` accounted for
    # ZERO, so they were deliberately NOT added as unvalidated breadth.
    parts = path.parts
    for i, part in enumerate(parts[1:], 1):
        if part == 'specs' and parts[i - 1] in ('tests', 'test'):
            return False
    if TEST_FILE.search(path.name) or TEST_DIRS & set(parts):
        return True
    return path.name[:-len(path.suffix)] in TEST_STEMS


# A '/' right after one of these starts a regex literal rather than dividing.
# JavaScript's division-versus-regex ambiguity only has to be resolved well
# enough to keep the paren count honest.
#
# '<' is deliberately NOT in this set. A JSX closing tag is '</p>', so treating
# the '/' as a regex start swallows the rest of the file and unbalances the
# paren count: preact's `expect(() => render(<p ...>foo</p>, scratch))` was
# reported matcherless although `.to.not.throw()` sits right after its closing
# paren. A real regex directly after '<' ('x < /re/.source') is vanishingly
# rare next to JSX. '>' stays, because `=> /re/.test(x)` is common.
REGEX_LEAD = set('(,=:[!&|?{;+-*%~^>') | {'\n'}


def skip_ws_and_comments(text: str) -> str:
    """Drop leading whitespace and // or /* */ comments.

    A wrapped matcher can be separated from its closing paren by a comment, and
    tailwindcss does exactly that:

        expect(
          await migrate(css`...`),
        )
          // NOTE: The `html {}` is not wrapped in a `@layer` directive ...
          .toEqual(css`...`)

    Checking only for whitespace before the '.' reported that as matcherless.
    """
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if text.startswith('//', i):
            j = text.find('\n', i)
            if j < 0:
                return ''
            i = j + 1
            continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            if j < 0:
                return ''
            i = j + 2
            continue
        break
    return text[i:]


def match_paren(text, open_index):
    """Index just past the ) that closes the ( at open_index, or None.

    Strings, template literals and REGEX LITERALS are all stepped over, so a
    paren inside one cannot unbalance the count. The regex case is not
    theoretical: prisma's `sql.match(/\\(DEFAULT, /g)` carries an escaped open
    paren inside a regex, and counting it reported a correctly-matched
    `expect(...).toBe(2)` as matcherless.
    """
    depth = 0
    i = open_index
    n = len(text)
    while i < n:
        c = text[i]
        if c == '/' and text[i + 1:i + 2] == '/':
            # A // comment. Skipping it matters more than it looks: an
            # apostrophe in prose ("the runner's check") otherwise opens a
            # string that swallows real parens, which reported a correctly
            # chained `await expect(...).rejects.toThrow(...)` in prisma as
            # matcherless.
            nl = text.find('\n', i)
            i = n if nl == -1 else nl
            continue
        elif c == '/' and text[i + 1:i + 2] == '*':
            close = text.find('*/', i + 2)
            i = n if close == -1 else close + 2
            continue
        elif c in '\'"`':
            quote = c
            i += 1
            while i < n:
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
        elif c == '/' and i + 1 < n:
            prev = text[:i].rstrip()
            # TypeScript's postfix non-null assertion makes `!` ambiguous. In
            # `!/re/.test(s)` the `!` is a prefix operator and a regex follows,
            # but in `node.width! / node.height!` it binds to the identifier
            # and the slash is division. mermaid has four of the latter, and
            # reading them as a regex ran to end of line and swallowed the
            # matcher, so `expect(a! / b!).toBeGreaterThanOrEqual(...)` was
            # reported as having none. Same class as the JSX `</p>` fix that
            # took nock from 1 hit to 11.
            postfix_bang = (len(prev) >= 2 and prev[-1] == '!'
                            and (prev[-2].isalnum() or prev[-2] in '_$)]'))
            if prev and prev[-1] in REGEX_LEAD and not postfix_bang:
                i += 1
                in_class = False
                while i < n:
                    if text[i] == '\\':
                        i += 2
                        continue
                    if text[i] == '[':
                        in_class = True
                    elif text[i] == ']':
                        in_class = False
                    elif text[i] == '/' and not in_class:
                        break
                    elif text[i] == '\n':
                        break          # unterminated, so it was division
                    i += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def string_spans(text: str):
    """Half-open spans of text that sit INSIDE a string or template literal.

    Returns SPANS rather than a blanked copy of the source on purpose: the Rust
    scanner's 336 false positives came from rewriting the text and losing offset
    alignment. Membership testing keeps every offset exact.

    A `${...}` region inside a template literal is CODE, so it is excluded from
    the span and an `expect(` there is still reported. Comments are consumed so
    that an apostrophe in prose does not open a string.

    Why this matters: an ESLint rule's tests carry the code under lint as string
    literals. playwright-community/eslint-plugin-playwright has nine
    `expect("something")` samples inside `code:` template literals, and every
    one was reported as a dead assertion.
    """
    spans, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n:
            nxt = text[i + 1]
            if nxt == '/':
                j = text.find('\n', i)
                i = n if j < 0 else j + 1
                continue
            if nxt == '*':
                j = text.find('*/', i + 2)
                i = n if j < 0 else j + 2
                continue
        if c in '"\'':
            j, start = i + 1, i + 1
            while j < n and text[j] != c:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '\n':      # unterminated: a quote used as prose
                    break
                j += 1
            if j < n and text[j] == c:
                spans.append((start, j))
                i = j + 1
                continue
            i += 1
            continue
        if c == '`':
            j, chunk = i + 1, i + 1
            while j < n and text[j] != '`':
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '$' and j + 1 < n and text[j + 1] == '{':
                    spans.append((chunk, j))      # literal text before ${
                    depth, j = 1, j + 2
                    while j < n and depth:
                        if text[j] == '{':
                            depth += 1
                        elif text[j] == '}':
                            depth -= 1
                        j += 1
                    chunk = j                      # literal text resumes here
                    continue
                j += 1
            if j < n:
                spans.append((chunk, j))
                i = j + 1
                continue
            i += 1
            continue
        i += 1
    return spans


def scan(path):
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []

    if defines_own_expect(text):
        return []

    hits = []
    import bisect
    spans = string_spans(text)
    starts = [a for a, _ in spans]
    for m in CALL.finditer(text):
        # Inside a string or template literal this is a code SAMPLE, not an
        # assertion. See string_spans for why this is a membership test.
        k = bisect.bisect_right(starts, m.start()) - 1
        if k >= 0 and m.start() < spans[k][1]:
            continue
        # A commented-out `expect(` is a disabled test, not a dead assertion.
        # hoppscotch keeps five of them in detectContentType.spec.js under
        # "// TODO: Figure this test situation", every line prefixed with //,
        # and all five were reported because CALL.finditer runs on the raw text
        # while comments were only skipped inside match_paren. Checked per line
        # rather than with a file-wide comment mask, because blanking literals
        # file-wide is what desynchronised the Rust scanner on raw strings.
        line_start = text.rfind('\n', 0, m.start()) + 1
        if text[line_start:m.start()].lstrip().startswith(('//', '*', '/*')):
            continue
        end = match_paren(text, m.end() - 1)
        if end is None:
            continue
        # What follows the closing paren decides it. A matcher continues with
        # '.', anything else means the assertion was discarded.
        rest = text[end:]
        tail = rest.lstrip(' \t')
        if tail.startswith(('.', '?.')):
            continue
        # A newline then '.' is still a chain, just wrapped.
        stripped = rest.lstrip()
        if stripped.startswith(('.', '?.')):
            continue
        # ... and a comment between the paren and the matcher is still a chain.
        if skip_ws_and_comments(rest).startswith(('.', '?.')):
            continue
        # `expect(...)` used as a value rather than a statement is not a no-op.
        # What FOLLOWS catches `foo(expect(w))`; what PRECEDES is needed for
        # `const e = expect(z);`, which the follows-check alone reads as a
        # discarded statement.
        if tail[:1] in (')', ',', ']', '}', ':', '=', '&', '|', '?'):
            continue
        before = text[:m.start()].rstrip()
        if before[-1:] in ('=', '(', ',', '[', ':', '?', '&', '|', '+', '!', '>'):
            continue
        if re.search(r'\breturn$', before):
            continue
        if not tail.startswith(';') and not tail.startswith('\n'):
            continue
        # chai's `should` style asserts INSIDE the argument, so
        # `expect(x.should.be.eql({...}))` is redundant, not dead. typeorm
        # writes ~120 of these and every one is a real assertion.
        arg = text[m.end():end - 1]
        if '.should.' in arg or arg.rstrip().endswith('.should'):
            continue
        line = text[:m.start()].count('\n') + 1
        snippet = ' '.join(text[m.start():end].split())[:70]
        hits.append((line, snippet))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roots', nargs='+')
    ap.add_argument('--all-files', action='store_true',
                    help='scan every js/ts file, not just *.test.* and *.spec.*')
    args = ap.parse_args()

    files = 0
    total = 0
    for root in args.roots:
        for path in pathlib.Path(root).rglob('*'):
            if not path.is_file() or SKIP_DIRS & set(path.parts):
                continue
            if not args.all_files and not is_test_file(path):
                continue
            if args.all_files and path.suffix not in JS_SUFFIX:
                continue
            files += 1
            for line, snippet in scan(path):
                print(f'{path}:{line}  {snippet}')
                total += 1
    print(f'-- {total} matcherless expect(s) in {files} test file(s) '
          f'across {len(args.roots)} root(s)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
