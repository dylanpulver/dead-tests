# Expected: exactly 2 findings

Written before the scanner existed. requires-python is ">=3.10,<3.15",
so the supported minors are 3.10, 3.11, 3.12, 3.13, 3.14.

FINDINGS (condition is true on every supported version, so the test runs nowhere):
1. test_never_runs_lower_bound   -- sys.version_info >= (3, 10)
2. test_never_runs_equality      -- sys.version_info[:2] != (3, 9)

NOT findings:
- test_always_runs               -- < (3, 10) is false everywhere, so it never skips
- test_partially_skipped         -- < (3, 12) is true on 3.10 and 3.11 only
- test_never_skipped_above_range -- >= (3, 15) is outside the range, never true
- test_platform_gate...          -- not a sys.version_info condition
- test_unconditional_skip        -- a maintainer parked it on purpose
