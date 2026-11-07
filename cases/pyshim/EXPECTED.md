# Expected: exactly 2 findings

requires-python is ">=3.10", so supported minors are 3.10 through 3.14.

FINDINGS:
1. pkg/compat.py dead_body  -- `if sys.version_info < (3, 10)` is false everywhere, body is dead
2. pkg/compat.py dead_else  -- `if sys.version_info >= (3, 10)` is true everywhere, else is dead

NOT findings:
- still_branches    -- < (3, 12) is true on 3.10 and 3.11 only
- platform_branch   -- not a version check
- awaits_future     -- >= (3, 15) is above the supported range, forward-looking
- refuses_by_writing -- refuses by writing a message and returning a code, which is a guard
  even though it never raises
- maintainer_said_keep_it -- carries `# noqa: UP036`, so the maintainer already decided
- refuses_old_interpreter -- the body only raises, so it is a guard refusing an
  interpreter rather than a shim adapting to one
- setup.py          -- a pre-install guard runs before the floor applies, must be excluded
- tests/test_shim.py -- test files belong to the other scanner
- platform_and_version -- `sys.platform == "win32" and version_info < (3, 14)` is live on
  Windows, so a verdict must hold across platforms as well as versions
- exact_patch_release -- `version_info[:3] == (3, 12, 5)` is true on a real
  interpreter, so a verdict must hold across micro versions, not just micro 0
