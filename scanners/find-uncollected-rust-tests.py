#!/usr/bin/env python3
"""Find Rust functions that look like tests but carry no test attribute.

Rust collects by ATTRIBUTE, not by name, which is the seam class that pays:
a `fn` inside `#[cfg(test)] mod tests` without `#[test]` compiles, is never
run, and nothing warns. Same shape as a .NET method missing `[Test]` or a
JUnit 5 method missing `@Test`, and unlike Go or PHP, the name carries no
signal either way, so a dropped attribute leaves nothing behind.

Only two places are searched, because only there is "a bare fn" anomalous:

  * inside a `#[cfg(test)]` module, at any nesting depth
  * a file under a top-level `tests/` directory (Rust's integration harness,
    where every free function is a candidate test)

Everything else in a crate is production code where a bare `fn` is normal.

SUPPRESSIONS, each one a mechanism the author used to say "deliberate":

  takes arguments    a test harness calls tests with no arguments, so any
                     parameter makes it a helper
  returns a value    `-> T` is a fixture or builder, not a test
  called in-tree     a function another test calls is a shared body; this is
                     the dominant false-positive class
  any test attribute `#[tokio::test]`, `#[rstest]`, `#[proptest]`,
                     `#[quickcheck]`, `#[wasm_bindgen_test]` and friends all
                     collect, so only a function with NO attribute at all is
                     reported
  #[ignore]          the author switched it off on purpose
  #[cfg(...)]        gated on a platform or feature, which is a decision
  macro-generated    a file containing `macro_rules!` is skipped, since the
                     real tests may be expanded rather than written out
  asserts nothing    a body with no assert!/panic!/unwrap/expect/? is a
                     helper that happens to take no arguments
  pub fn             a public item in a test module is exported for other
                     modules to use

Written after the .NET and JUnit scanners showed that attribute seams yield
where name-prefix seams do not (memory: attribute-seams-beat-prefix-seams).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

SKIP_DIRS = {'.git', 'target', 'node_modules', 'vendor', '_vendor', 'vendored',
             'third_party', 'thirdparty', 'externals', 'bundled', 'patched',
             '.cargo', 'fixtures', 'testdata'}

# A test attribute is anything whose final path segment is `test`, `bench` or
# ends in `_test`: #[test], #[tokio::test], #[async_std::test],
# #[wasm_bindgen_test], #[googletest::test]. Plus the generators, which attach
# to a function that then has no #[test] of its own.
TEST_ATTR = re.compile(
    r'^\s*#\s*\[\s*(?:[\w:]+::)?'
    r'(?:test|bench|rstest|proptest|quickcheck|test_case|values|case|'
    r'parameterized|template|apply|fixture|googletest|wasm_bindgen_test|'
    r'tokio_test|serial|serial_test|file_serial|traced_test|test_log|'
    r'test_context|named|instrument)\b')

# Any attribute at all. A function carrying an unrecognised attribute is left
# alone rather than guessed at: the cost of a wrong report is a maintainer
# reading a PR that says their working test does not run.
ANY_ATTR = re.compile(r'^\s*#\s*\[')

FN = re.compile(
    r'^(?P<indent>[ \t]*)(?P<vis>pub(?:\s*\([^)]*\))?\s+)?'
    r'(?:const\s+|async\s+|unsafe\s+|extern\s+"[^"]*"\s+)*'
    r'fn\s+(?P<name>[A-Za-z_]\w*)\s*'
    r'(?P<generics><[^>]*>)?\s*'
    r'\((?P<args>[^)]*)\)'
    r'(?P<ret>\s*->\s*[^{;]+)?\s*(?P<open>\{)?', re.M)

ASSERTING = re.compile(
    r'\b(?:assert|assert_eq|assert_ne|debug_assert|debug_assert_eq|'
    r'debug_assert_ne|panic|unreachable|todo|unimplemented|'
    r'assert_matches|assert_snapshot|assert_debug_snapshot|'
    r'assert_yaml_snapshot|assert_json_snapshot|insta)\s*!'
    r'|\.unwrap\(\)|\.expect\(|\.unwrap_err\(\)|\.assert\(\)'
    r'|\bshould\b')

CFG_TEST = re.compile(r'^\s*#\s*\[\s*cfg\s*\(\s*test\s*\)\s*\]')


def strip_comments(text: str) -> str:
    """Blank out // and /* */ comments, preserving offsets and newlines.

    Offsets must survive because every report is a line number, and a
    commented-out copy of a function must not look like a definition. That
    second case is not theoretical: in jackson-core an assertion appeared
    twice and one copy was commented out, which defeated a text count.
    """
    out = list(text)
    i, n = 0, len(text)
    in_line = in_block = in_str = in_char = False
    depth = 0
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if in_line:
            if c == '\n':
                in_line = False
            else:
                out[i] = ' '
        elif in_block:
            if c == '*' and nxt == '/':
                depth -= 1
                out[i] = out[i + 1] = ' '
                i += 2
                if depth == 0:
                    in_block = False
                continue
            if c == '/' and nxt == '*':
                depth += 1
                out[i] = out[i + 1] = ' '
                i += 2
                continue
            if c != '\n':
                out[i] = ' '
        elif in_str:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                in_str = False
        elif in_char:
            if c == '\\':
                i += 2
                continue
            if c == "'":
                in_char = False
        else:
            if c == '/' and nxt == '/':
                in_line = True
                out[i] = ' '
            elif c == '/' and nxt == '*':
                in_block = True
                depth = 1
                out[i] = out[i + 1] = ' '
                i += 2
                continue
            elif c == '"':
                in_str = True
            elif c == "'":
                # A lifetime (`&'a T`) is not a char literal. Only treat it as
                # one when a closing quote plausibly follows.
                rest = text[i:i + 4]
                if re.match(r"'(?:\\.|[^\\'])'", rest):
                    in_char = True
        i += 1
    return ''.join(out)


def body_of(text: str, open_brace: int) -> str:
    """Source between the { at open_brace and its matching }."""
    depth = 0
    for j in range(open_brace, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                return text[open_brace + 1:j]
    return text[open_brace + 1:]


def cfg_test_spans(lines: list[str]) -> list[tuple[int, int]]:
    """(start_line, end_line) for every `#[cfg(test)] mod ... { }`, 1-based."""
    spans = []
    for idx, line in enumerate(lines):
        if not CFG_TEST.match(line):
            continue
        # The `mod` may be on this line or a later one; attributes can stack.
        k = idx + 1
        while k < len(lines) and (ANY_ATTR.match(lines[k])
                                  or not lines[k].strip()):
            k += 1
        if k >= len(lines) or not re.search(r'\bmod\s+\w+', lines[k]):
            continue
        # Walk braces from the mod line to find the end.
        depth, started, end = 0, False, k
        for j in range(k, len(lines)):
            depth += lines[j].count('{') - lines[j].count('}')
            if '{' in lines[j]:
                started = True
            if started and depth <= 0:
                end = j
                break
        else:
            end = len(lines) - 1
        spans.append((k + 1, end + 1))
    return spans


def attributed_lines(text: str) -> set[int]:
    """1-based line numbers of items that carry at least one attribute.

    Scanned FORWARD, matching each `#[` to its balanced `]`, rather than
    walking up from the fn line. A backward line walk cannot see past the `)]`
    of a wrapped attribute, and that is the common shape: arrow-rs and pest
    both write

        #[should_panic(
            expected = "Need at least ... bytes in buffers[0] ..."
        )]
        fn test_fixed_width_overflow() {

    which made every one of those read as unattributed. 85 candidates across
    two repos were all this single class.
    """
    attributed = set()
    lines = text.splitlines()
    i = 0
    n = len(text)
    while True:
        j = text.find('#[', i)
        if j < 0:
            break
        # `#!` is an inner attribute for the enclosing module, not an item.
        if text[j + 1:j + 3] == '![':
            i = j + 2
            continue
        depth = 0
        k = j + 1
        while k < n:
            c = text[k]
            # A bracket inside a char or byte literal is payload, not nesting.
            # tailwindcss writes `#[bytes(b'[')]`, and counting that `[` left the
            # depth unbalanced, so this scan ran on to the next `]` far below and
            # every attribute after it was missed: two `#[test]` functions in that
            # file were reported uncollected with the attribute directly above
            # them. Scoped to this loop on purpose, since blanking literals
            # file-wide desynchronised on Rust raw strings (`r#"..."#`) and turned
            # 8 false positives into 336.
            if c == "'" and re.match(r"'(?:\\.|[^\\'])'", text[k:k + 4]):
                k += 3
                continue
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    break
            k += 1
        if k >= n:
            break
        # The attributed item is the next line with code on it, skipping
        # blanks, doc comments and further attributes (which this loop will
        # also visit on their own).
        line_after = text[:k].count('\n') + 2
        idx = line_after - 1
        while idx < len(lines):
            stripped = lines[idx].strip()
            if not stripped or stripped.startswith(('///', '//!')):
                idx += 1
                continue
            if stripped.startswith('#['):
                break  # handled by its own iteration
            attributed.add(idx + 1)
            break
        i = k + 1
    return attributed


def scan(path: pathlib.Path, in_tests_dir: bool):
    raw = path.read_text(encoding='utf-8', errors='replace')
    if 'macro_rules!' in raw:
        return
    text = strip_comments(raw)
    lines = text.splitlines()
    rawlines = raw.splitlines()

    spans = cfg_test_spans(lines)
    if not spans and not in_tests_dir:
        return

    def inside_test_scope(lineno: int) -> bool:
        if in_tests_dir:
            return True
        return any(a <= lineno <= b for a, b in spans)

    attributed = attributed_lines(text)

    # Every call site in the file, so a shared body is not reported.
    called = set(re.findall(r'(?<![\w.:])([a-z_]\w*)\s*\(', text))

    for m in FN.finditer(text):
        lineno = text[:m.start()].count('\n') + 1
        name = m.group('name')
        if not inside_test_scope(lineno):
            continue
        if m.group('vis'):
            continue
        if m.group('args').strip():
            continue
        if m.group('ret'):
            continue
        # rustc rejects `#[test]` on a generic function outright, so a generic
        # fn is never a dropped attribute. arrow-rs's
        # `test_decimal_roundtrip<T: DecimalType>()` is a helper invoked as
        # `test_decimal_roundtrip::<Decimal128Type>()`, which the plain
        # `name(` call count below also misses.
        if m.group('generics'):
            continue
        if name == 'main':
            continue
        # Any attribute at all means a decision was recorded here.
        if lineno in attributed:
            continue
        if not m.group('open'):
            continue
        body = body_of(text, m.end('open') - 1)
        if not ASSERTING.search(body):
            continue
        # Any mention beyond the declaration means the function is reachable,
        # and the mention need not be a call: pest passes its test bodies as
        # BARE FN POINTERS so it can run them on threads with a fixed stack
        # (`on_fixed_stacks("name", check_depth)`), and mise registers a hook
        # with `run_before_main!(init)`. Counting only `name(` reported all
        # five of those as uncollected.
        decls = len(re.findall(r'\bfn\s+' + re.escape(name) + r'\b', text))
        mentions = len(re.findall(r'(?<![\w.])' + re.escape(name) + r'\b', text))
        if mentions - decls > 0:
            continue
        snippet = rawlines[lineno - 1].strip() if lineno <= len(rawlines) else ''
        yield lineno, name, snippet


def rust_files(root: pathlib.Path):
    for f in sorted(root.rglob('*.rs')):
        if SKIP_DIRS & set(f.parts):
            continue
        # `tests/` must be a crate's own integration directory, i.e. a sibling
        # of a Cargo.toml, not any directory that happens to be called tests.
        in_tests = False
        for i, part in enumerate(f.parts):
            if part == 'tests' and (pathlib.Path(*f.parts[:i]) / 'Cargo.toml').exists():
                in_tests = True
                break
        yield f, in_tests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('roots', nargs='+')
    args = ap.parse_args()
    total = files = 0
    for root in args.roots:
        for path, in_tests in rust_files(pathlib.Path(root)):
            files += 1
            try:
                for lineno, name, snippet in scan(path, in_tests):
                    print(f'{path}:{lineno}: {name}()  {snippet}')
                    total += 1
            except (OSError, RecursionError):
                continue
    print(f'-- {total} uncollected rust test(s) from {files} .rs file(s)',
          file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
