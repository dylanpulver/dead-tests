#!/usr/bin/env python3
"""Find calls to same-file async functions that are never awaited.

Two shapes, and only the second is novel:

  bare        a bare `coro()` statement, so the coroutine is created and dropped
  bound       `r = coro()` where `r` is never awaited in that function, so the
              code goes on to use a coroutine object as if it were the value

**mypy already reports the bare shape** as `[unused-coroutine]` with "Are you
missing an await?", and it does so by default. It does NOT report the bound
shape, because binding counts as using. That is the shape that produced
rthalley/dnspython#1400, where `r = dns.asyncquery.https(...)` lost its `await`
and `q.is_response(r)` was handed a coroutine. Nothing caught it because the
test was never collected and the test tree is excluded from type checking.

Resolution is deliberately same-file only: a function is treated as async solely
when this module defines it with `async def`. Cross-module inference would need
imports resolved and would trade the precision that makes the output worth
reading.

Calls appearing as arguments to another call are never reported, since
`create_task(coro())`, `gather(coro(), ...)` and `asyncio.run(coro())` all pass
the coroutine on purpose.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

SKIP_DIRS = {'.git', 'build', 'dist', 'node_modules', '.tox', 'venv',
             'site-packages', 'vendor', '.eggs', '__pypackages__', 'mutants'}


def is_async_generator(node: ast.AsyncFunctionDef) -> bool:
    """An `async def` containing a yield is an async generator, not a coroutine.

    Calling one returns an async generator that you `async for` over or drive
    with .asend()/.athrow(), and awaiting it is wrong. `agen = agen_func()` is
    therefore correct code, and treating these as coroutines was the dominant
    false positive once attribute calls were excluded.
    """
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Yield, ast.YieldFrom)):
            # A yield inside a nested def belongs to that def, not to this one.
            return True
    return False


def async_defs(tree: ast.AST) -> set[str]:
    """Coroutine functions this module defines whose call returns a coroutine.

    Excludes async generators, and excludes any decorated `async def`: a
    decorator can change what calling it returns. prefect's `@flow` and `@task`
    hand back a state rather than a coroutine, and assuming otherwise produced
    most of what survived the earlier filters.
    """
    return {n.name for n in getattr(tree, 'body', [])
            if isinstance(n, ast.AsyncFunctionDef)
            and not is_async_generator(n)
            and not n.decorator_list}


def argument_calls(func: ast.AST) -> set[int]:
    """id() of every Call node that sits inside another call's arguments."""
    inside = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        for arg in list(node.args) + [k.value for k in node.keywords]:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Call):
                    inside.add(id(sub))
    return inside


def consumed_names(func: ast.AST) -> set[str]:
    """Names the function hands off rather than treats as a plain value.

    Awaited directly, passed to any call, or returned. All three are deliberate
    coroutine handling: `await c`, `await shield(c)`, `create_task(c)`,
    `return c`. Only a name that is bound and then used as if it were already
    the result is suspicious.
    """
    out = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Name):
            out.add(node.value.id)
        elif isinstance(node, ast.Call):
            for arg in list(node.args) + [k.value for k in node.keywords]:
                if isinstance(arg, ast.Name):
                    out.add(arg.id)
                elif isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
                    out.add(arg.value.id)
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
            out.add(node.value.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            # `c.send(None)`, `c.close()`, `c.throw(...)`: driving a coroutine
            # object by hand, which CPython's own test suite does constantly.
            out.add(node.value.id)
    return out


def own_statements(func: ast.AST):
    """Statements belonging to this function, not to a def nested inside it.

    `ast.walk` descends into nested defs, so without this every finding inside a
    nested function was reported twice, once per enclosing def.
    """
    stack = [func]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Lambda)):
                continue
            stack.append(child)


def called_name(call: ast.Call) -> str:
    """Only a bare `name()` call resolves.

    An attribute call cannot be matched by its attribute alone: `path.resolve()`
    is not this module's `async def resolve`, and keying on the attribute name
    was most of a 3315-finding flood when this was first measured.
    """
    f = call.func
    return f.id if isinstance(f, ast.Name) else ''


def scan(path: Path, text: str, tree: ast.AST):
    coros = async_defs(tree)
    if not coros:
        return
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        in_args = argument_calls(func)
        awaited = consumed_names(func)
        for stmt in own_statements(func):
            # bare: `coro()` as a statement on its own
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if called_name(call) in coros and id(call) not in in_args:
                    yield stmt.lineno, func.name, called_name(call), 'bare'
            # bound: `r = coro()` with r never awaited in this function
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                call = stmt.value
                if not isinstance(call, ast.Call):
                    continue
                if called_name(call) not in coros or id(call) in in_args:
                    continue
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                if names and not any(n in awaited for n in names):
                    yield (stmt.lineno, func.name, called_name(call),
                           f'bound to {names[0]}, never awaited')


def py_files(root: Path):
    for f in sorted(root.rglob('*.py')):
        if set(f.parts) & SKIP_DIRS:
            continue
        if any(d.startswith(('.venv', 'venv', '.env', '.pixi', '.conda'))
               for d in f.parts):
            continue
        yield f


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    found = scanned = 0
    for path in py_files(root):
        try:
            text = path.read_text(errors='replace')
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        scanned += 1
        for lineno, where, coro, why in scan(path, text, tree):
            print(f'{path.relative_to(root)}:{lineno}: {where} calls '
                  f'{coro}() without await ({why})')
            found += 1
    print(f'-- {found} unawaited call(s) from {scanned} python file(s)',
          file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
