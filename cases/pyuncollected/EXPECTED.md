# Expected: exactly 2 candidates

Written before running the scanner.

1. tests/test_fixture_cases.py: function real_uncollected_test
2. tests/test_fixture_cases.py: method TestSomething.method_uncollected

Must NOT be flagged:
- mypy_test_parked, notest_parked, mypy_test_method_parked (park prefixes)
- helper_used (takes a non-fixture argument, and is referenced)
- test_already_prefixed, TestSomething.test_real_method (already collected)

## Label change, 2026-11-02 (count unchanged, still exactly 2)

`TestSomething.method_uncollected` is now reported as a **dead helper**, not as
an uncollected test, because its name does not start with `test`. The two
findings wear the same shape but are different things and are fixed differently:
a `test_*` method was MEANT to be collected and is not, while a differently
named one was meant to be CALLED, so an uncalled one is dead code.

InvenTree forced the distinction. `ViewTests.get_index_page` asserts a 200 and
its docstring says "used for subsequent unit tests", yet nothing calls it.
Reporting that as "never collected" reads as a dead test, which it is not.

## Added after Pillow (a module with no collected test is a manual harness)

- `tests/test_manual_harness.py` -> nothing. Pillow's `Tests/test_uploader.py`
  holds only `check_upload_equal` and `check_upload_similar`, which exist to
  FAIL so a developer can verify the error-image uploader: helper.py's
  `assert_image_equal` calls `upload(a, b)` before `pytest.fail`. They are named
  `check_*` precisely so pytest never collects them.

  **A forgotten test is recognised by its siblings running while it does not.**
  A module with no collected test at all did not lose one, so the scan now
  requires at least one collected test in the file before reporting anything
  in it.

Expected total remains 2, both in `test_fixture_cases.py`.

## Added after dnspython (a capital `Test` prefix is a test, not a helper)

- `TestCapitalPrefix.TestDoH3PostRequest` must be reported as **"is never
  collected"**, not as a dead helper. pytest collects only a lowercase `test`
  prefix, so the capital T IS the bug. Matching the prefix case-sensitively
  labelled dnspython's two DoH3 methods as dead helpers, which is the opposite
  of what our own open PR there (#1400) says about them.

Expected total is now 3.

## Correction, 2026-11-02: the non-`test` label is now NEUTRAL

`TestSomething.method_uncollected` was labelled "dead helper, not an uncollected
test". **That asserted a distinction the tool cannot make.** xarray has
`TestContour.list_of_colors_in_cmap_raises_error` and
`TestPydapOnline.output_grid_deprecation_warning_dap2dataset`, which read as test
descriptions, and the first is already queued for Dylan as an uncollected TEST,
which is the opposite claim. readthedocs' `add_project_to_team` and trimesh's
`sample_volume_rectangular` read as actions a helper performs.

Both kinds now print the same neutral line, which says what is true and what to
check: `X.y() asserts, is not collected, and nothing calls it (read it: a
forgotten test, or dead helper code)`.

A name starting with `test` in any case still prints "is never collected",
because there the intent is unambiguous.

## Added after readthedocs (a parameterised method is a helper by construction)

- `TestParameterisedHelper.add_project_to_team` must NOT be reported.
  readthedocs' real one takes `(self, team="foobar", projects=None, test=True)`
  and returns the response. **A method taking anything beyond `self` and
  pytest's builtin fixtures cannot be collected as a test at all**, so it is a
  helper however it is named, and whether anything calls it is a dead-code
  question rather than a dead-test one.

  The module-level function branch already applied this check; the method branch
  did not, which is why readthedocs reported two.

Expected total is now 3 (the fixture's own case is also called, so it is
suppressed on two independent grounds).
