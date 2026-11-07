#!/usr/bin/env python3
"""Find `if sys.version_info ...` branches in production code that cannot run.

A package that once supported 3.7 and now declares `requires-python = ">=3.12"`
keeps every compatibility branch it ever wrote, and the ones guarding older
interpreters are now dead code. Nobody decided that, which is what separates
this from a skip someone chose.

Two shapes are reported:

  dead-body  the condition is false on every supported version
  dead-else  the condition is true on every supported version, so the else is dead

`setup.py` is excluded: a pre-install guard legitimately inspects whatever
interpreter is running, before the floor applies. Test files are excluded too,
since `find-stale-version-gates.py` covers the `skipif` form.

The evaluator is imported from find-stale-version-gates.py rather than copied,
so the two tools cannot drift on what "always true" means.
"""
from __future__ import annotations

import ast
import importlib.util
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


_SIBLING = Path(__file__).with_name('find-stale-version-gates.py')
_spec = importlib.util.spec_from_file_location('_gates', _SIBLING)
_gates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gates)

supported_minors = _gates.supported_minors
mentions_version_info = _gates.mentions_version_info
evaluate = _gates.evaluate
awaits_future = _gates.awaits_future
foreign_copyright = _gates.foreign_copyright
SKIP_DIRS = _gates.SKIP_DIRS

# A version check in any of these is about the environment rather than about
# the package's own supported range.
SKIP_NAMES = {'setup.py', 'conftest.py', '_version.py', 'versioneer.py'}

# Vendored code keeps its upstream's supported range, not ours. Every finding in
# airflow's _vendor, joblib's externals, pyinstaller's waflib and pandas's
# subprojects was of this kind.
VENDOR_DIRS = {'_vendor', '_vendored', 'vendored', 'externals', 'third_party',
               'thirdparty', 'subprojects', 'waflib', 'bundled',
               # pipenv keeps a patched copy of pip under pipenv/patched/, which
               # carries pip's supported range and is re-vendored from upstream.
               'patched'}


def is_guard(node: ast.If) -> bool:
    """True when the branch exists to refuse an interpreter, not to adapt to one.

    A guard raises or exits and nothing else: pyinstaller's `check_requirements`
    raises EnvironmentError below 3.8, and pipx, sqlfluff, yt-dlp and pdm's
    installer all do the same in `__init__.py` or an install script. Those run
    before or outside the package's declared range on purpose, since metadata can
    be bypassed, so removing one is a behaviour change rather than a cleanup.
    A shim, by contrast, imports or assigns.
    """
    body = node.body
    if not body:
        return False
    refuses = False
    for stmt in body:
        if isinstance(stmt, ast.Raise):
            refuses = True
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            func = stmt.value.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            if name in ('exit', '_exit', 'write', 'print', 'error', 'fatal',
                        'critical'):
                refuses = True
                continue
        if isinstance(stmt, ast.Return):
            continue
        return False
    return refuses


def production_files(root: Path):
    for f in sorted(root.rglob('*.py')):
        if set(f.parts) & SKIP_DIRS:
            continue
        if any(d.startswith(('.venv', 'venv', '.env', '.pixi', '.conda'))
               for d in f.parts):
            continue
        if set(f.parts) & VENDOR_DIRS:
            continue
        if f.name in SKIP_NAMES:
            continue
        if f.name.startswith('test_') or f.name.endswith('_test.py'):
            continue
        if 'tests' in f.parts or 'test' in f.parts:
            continue
        yield f


def enclosing_name(tree: ast.AST, target: ast.AST) -> str:
    """The function or class a node sits in, for a readable report."""
    best = '<module>'
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        for child in ast.walk(node):
            if child is target:
                best = node.name
                break
    return best


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    minors, spec = supported_minors(root)
    if not minors:
        print(f'-- no usable requires-python in {root.name} '
              f'({spec or "not found"}), cannot judge a shim', file=sys.stderr)
        return 0

    found = 0
    for path in production_files(root):
        try:
            text = path.read_text(errors='replace')
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        foreign = foreign_copyright(text, root)
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            if not mentions_version_info(node.test):
                continue
            verdict = evaluate(node.test, minors)
            if verdict == 'never':
                kind = 'dead-body'
            elif verdict == 'always' and node.orelse:
                kind = 'dead-else'
            else:
                continue
            if awaits_future(node.test, minors):
                continue
            if kind == 'dead-body' and is_guard(node):
                continue
            line = text.splitlines()[node.lineno - 1] if node.lineno <= len(
                text.splitlines()) else ''
            if 'UP036' in line:
                continue
            src = ast.get_source_segment(text, node.test) or '<condition>'
            where = enclosing_name(tree, node)
            rel = path.relative_to(root)
            tag = (f'  [check: header says "{foreign}", likely vendored]'
                   if foreign else '')
            print(f'{rel}:{node.lineno}: {kind} in {where} ({src}){tag}')
            found += 1

    print(f'-- {found} dead shim(s); supported minors 3.{minors[0]}'
          f'-3.{minors[-1]} from {spec!r}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
