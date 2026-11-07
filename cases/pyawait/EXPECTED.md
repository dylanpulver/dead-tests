# Expected: exactly 4 findings

Written before the detector existed.

FINDINGS:
1. bare_discarded        -- bare `inner()` statement, coroutine dropped
2. bound_never_awaited   -- `r = inner()` and r is never awaited in the function
3. sync_caller           -- bare `inner()` in a sync function
4. nested                -- bare `inner()` inside a nested def, reported ONCE,
   attributed to nested() and not also to has_nested_def()

NOT findings:
- bound_then_awaited     -- assigned, then `await c` later in the same function
- awaited_inline         -- `await inner()`
- handed_to_create_task  -- the call is an argument to create_task
- handed_to_gather       -- the calls are arguments to gather
- sync_runs_it           -- the call is an argument to asyncio.run

Note: mypy already reports cases 1 and 3 as [unused-coroutine] when it runs over
the file. Case 2 is the one mypy misses, because binding counts as using, and it
is the shape that produced the real dnspython bug.

## Known miss, and the reason this seam was abandoned

The motivating real bug was `r = dns.asyncquery.https(...)` with the `await`
lost. That is an attribute call on an imported module. Resolving it needs import
resolution plus the knowledge that the target is a coroutine function, which is
type information this detector does not have.

Allowing attribute calls to match by attribute name alone produced 3315 findings
across 60 repos, almost all of them wrong (`path.resolve()` matching an
`async def resolve`). Restricting to module-level bare-name calls gives 0
findings across the whole corpus. There is no middle setting: the precision and
the recall are controlled by the same switch.
