import asyncio


async def inner() -> int:
    return 1


async def bare_discarded():
    inner()                      # FINDING: coroutine created and dropped


async def bound_never_awaited():
    r = inner()                  # FINDING: used as if it were the value
    assert r == 1


async def bound_then_awaited():
    c = inner()
    return await c               # fine: deliberate two-step


async def awaited_inline():
    return await inner()         # fine


async def handed_to_create_task():
    t = asyncio.create_task(inner())
    return await t               # fine


async def handed_to_gather():
    return await asyncio.gather(inner(), inner())   # fine


def sync_caller():
    inner()                      # FINDING: sync code dropping a coroutine


def sync_runs_it():
    return asyncio.run(inner())  # fine: passed as an argument


async def has_nested_def():
    async def nested():
        inner()              # FINDING: belongs to nested(), reported once
    return nested


# The shape that motivated this detector, from rthalley/dnspython#1400:
#   r = dns.asyncquery.https(q, url, ...)      # await was lost
#   assert q.is_response(r)                    # r is a coroutine
# It is an attribute call on an imported module, so same-file bare-name
# resolution cannot see it. Recorded here as a KNOWN MISS, not a finding.
