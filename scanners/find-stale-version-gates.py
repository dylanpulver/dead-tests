#!/usr/bin/env python3
"""Find pytest skipif gates that are true on every Python the project supports.

A `@pytest.mark.skipif(sys.version_info >= (3, 12), ...)` written when the
project still supported 3.9 becomes a test that runs NOWHERE once the floor
rises past 3.12. Unlike an unconditional `@pytest.mark.skip`, nobody decided
that: the gate went stale underneath the test.

The check is computable. Read `requires-python`, enumerate the supported minor
versions, evaluate the condition for each, and report the gates that are true
for all of them.

Conditions are evaluated with a fake `sys`, and only after every node in the
expression passes a whitelist, so nothing from the scanned repository runs.
"""
from __future__ import annotations

import ast
import re
import sys
import warnings
from pathlib import Path

# Parsing other projects' sources emits THEIR SyntaxWarnings on our stderr, and
# in a multi-repo sweep those lines read exactly like findings: six repos looked
# like hits in one run and every line was a `<unknown>:215: SyntaxWarning` from
# the subject's own string literals. `<unknown>` is the giveaway, since a warning
# from this file would carry this path. Already fixed in
# find-dead-pytest-raises-assertions.py; carried here so the two cannot drift.
warnings.simplefilter('ignore', SyntaxWarning)


# No Call, no Lambda, no comprehension: a condition containing any of those is
# reported as unevaluated rather than executed.
SAFE_NODES = (
    ast.Expression, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.And, ast.Or,
    ast.Not, ast.Attribute, ast.Name, ast.Constant, ast.Tuple, ast.List,
    ast.Subscript, ast.Slice, ast.Load,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
    ast.In, ast.NotIn,
)

# Patch releases a condition might single out; 0 alone made black's
# `version_info[:3] == (3, 12, 5)` read as unreachable.
MICROS = (0, 1, 2, 3, 4, 5, 6, 7, 9, 12, 20)

# A condition can gate on the platform as well, and pinning one made prefect's
# `sys.platform == "win32" and sys.version_info < (3, 14)` read as unreachable
# when it is live on Windows.
PLATFORMS = ('linux', 'darwin', 'win32')

SKIP_DIRS = {'.git', 'build', 'dist', 'node_modules', '.tox', 'venv',
             'site-packages', 'vendor', '.eggs', '__pypackages__', 'mutants'}


class FakeSys:
    """Just enough `sys` for a version gate."""

    def __init__(self, minor: int, micro: int = 0, platform: str = 'linux'):
        self.version_info = (3, minor, micro, 'final', 0)
        self.platform = platform
        self.maxsize = 2 ** 63 - 1


# A copyright header naming someone unrelated to this project means the file was
# vendored, and a vendored file keeps its UPSTREAM's supported python range, not
# ours. kivy carries pycodestyle as kivy/tools/pep8checker/pep8.py, whose header
# reads "Copyright (C) 2006-2009 Johann C. Rocholl", and no directory on that
# path is a vendor marker, so VENDOR_DIRS cannot catch it.
#
# This TAGS rather than suppresses, copied deliberately from the .NET scanner's
# foreign_copyright so the two cannot drift: plenty of projects legitimately
# carry an individual author's name, so dropping on this signal would lose real
# findings. A tag puts the header in front of me while triaging, which is where
# the judgement belongs.
COPYRIGHT = re.compile(r'^\s*(?://+|#|\*|/\*)\s*(Copyright\b[^\n]{0,80})', re.M)


def foreign_copyright(text: str, root: Path) -> str:
    """The copyright line when it names someone other than this project."""
    m = COPYRIGHT.search(text[:2000])
    if not m:
        return ''
    line = m.group(1).strip()
    own = [w.lower() for w in re.split(r'[^A-Za-z]+', root.name) if len(w) > 3]
    if any(w in line.lower() for w in own):
        return ''
    return line


def supported_minors(root: Path) -> tuple[list[int], str]:
    """The 3.x minors allowed by requires-python, and the spec we read."""
    spec = ''
    for name in ('pyproject.toml', 'setup.cfg', 'setup.py'):
        p = root / name
        if not p.exists():
            continue
        text = p.read_text(errors='replace')
        m = re.search(r'^\s*(?:requires-python|python_requires)\s*=\s*["\']?([^"\'\n]+)',
                      text, re.M)
        if m:
            spec = m.group(1).strip()
            break
        # Poetry puts the floor in [tool.poetry.dependencies] instead, as
        # `python = "^3.9"`. 12 repos across the two corpora were reported
        # "cannot judge a shim" for this reason alone, textual and thefuck
        # among them, so the seam was never measured there.
        m = re.search(r'^\s*python\s*=\s*["\']([^"\'\n]+)["\']', text, re.M)
        if m:
            spec = m.group(1).strip()
            break
    if not spec:
        return [], ''

    lo, hi = 0, 99
    for part in spec.split(','):
        part = part.strip()
        m = re.match(r'(>=|>|<=|<|==|~=|\^|~)\s*3\.(\d+)', part)
        if not m:
            continue
        op, minor = m.group(1), int(m.group(2))
        # Poetry's caret and tilde. `^3.9` is >=3.9,<4.0; `~3.9` is
        # >=3.9,<3.10. Both pin the floor, which is all this needs.
        if op == '^':
            lo = max(lo, minor)
            continue
        if op == '~':
            lo = max(lo, minor)
            hi = min(hi, minor)
            continue
        if op == '>=':
            lo = max(lo, minor)
        elif op == '>':
            lo = max(lo, minor + 1)
        elif op == '<':
            hi = min(hi, minor - 1)
        elif op == '<=':
            hi = min(hi, minor)
        elif op in ('==', '~='):
            lo = max(lo, minor)
    if lo == 0:
        return [], spec
    # Nothing beyond 3.14 exists to run on, so an open upper bound stops there.
    hi = min(hi, 14)
    if hi < lo:
        return [], spec
    return list(range(lo, hi + 1)), spec


def mentions_version_info(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and n.attr == 'version_info':
            return True
    return False


def awaits_future(cond: ast.AST, minors: list[int]) -> bool:
    """True when the gate requires a Python newer than anything supported.

    A gate naming a minor above the supported ceiling is waiting for a release
    rather than stranded by a rising floor. `skipif(version < (3, 15))` on a
    project capped at 3.14 is one shape; a production `if version >= (3, 15)`
    is the other. The operator does not matter, only the version named.
    """
    for n in ast.walk(cond):
        if not isinstance(n, ast.Compare) or len(n.ops) != 1:
            continue
        if not mentions_version_info(n.left):
            continue
        target = n.comparators[0]
        if not isinstance(target, ast.Tuple) or len(target.elts) < 2:
            continue
        try:
            major = ast.literal_eval(target.elts[0])
            minor = ast.literal_eval(target.elts[1])
        except (ValueError, TypeError):
            continue
        if major == 3 and minor > minors[-1]:
            return True
    return False


def evaluate(cond: ast.AST, minors: list[int]) -> str:
    """'always', 'never', 'sometimes', or 'unevaluated'."""
    expr = ast.Expression(body=cond)
    for n in ast.walk(expr):
        if not isinstance(n, SAFE_NODES):
            return 'unevaluated'
    try:
        code = compile(ast.fix_missing_locations(expr), '<gate>', 'eval')
    except (SyntaxError, ValueError):
        return 'unevaluated'
    results = []
    for minor in minors:
        for micro in MICROS:
            for platform in PLATFORMS:
                try:
                    results.append(
                        bool(eval(code, {'sys': FakeSys(minor, micro, platform)}, {})))
                except Exception:
                    return 'unevaluated'
    if all(results):
        return 'always'
    if not any(results):
        return 'never'
    return 'sometimes'


def skipif_conditions(node: ast.AST):
    """Yield (decorator_source_line, condition_node) for each skipif."""
    for dec in getattr(node, 'decorator_list', []):
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
        if name != 'skipif' or not dec.args:
            continue
        yield dec, dec.args[0]


def test_files(root: Path):
    for f in sorted(root.rglob('*.py')):
        if set(f.parts) & SKIP_DIRS:
            continue
        if any(d.startswith(('.venv', 'venv', '.env', '.pixi', '.conda'))
               for d in f.parts):
            continue
        if f.name.startswith('test_') or f.name.endswith('_test.py'):
            yield f


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    minors, spec = supported_minors(root)
    if not minors:
        print(f'-- no usable requires-python in {root.name} '
              f'({spec or "not found"}), cannot judge a version gate',
              file=sys.stderr)
        return 0

    found = 0
    for path in test_files(root):
        try:
            text = path.read_text(errors='replace')
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        foreign = foreign_copyright(text, root)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                continue
            for dec, cond in skipif_conditions(node):
                if not mentions_version_info(cond):
                    continue
                if evaluate(cond, minors) != 'always':
                    continue
                if awaits_future(cond, minors):
                    continue
                rel = path.relative_to(root)
                src = ast.get_source_segment(text, cond) or '<condition>'
                tag = (f'  [check: header says "{foreign}", likely vendored]'
                       if foreign else '')
                print(f'{rel}:{node.lineno}: {node.name} is skipped on every '
                      f'supported version ({src}){tag}')
                found += 1

    print(f'-- {found} stale gate(s); supported minors 3.{minors[0]}'
          f'-3.{minors[-1]} from {spec!r}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
