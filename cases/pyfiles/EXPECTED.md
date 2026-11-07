# _pyfiles — expectations for find-uncollected-py-files.py

A whole file of tests whose NAME does not match the project's `python_files`
patterns is never imported by pytest, so every test inside is dead at once and
nothing warns, because to pytest the file simply is not a test file.

## Must be reported (1)

- `tests/helpers_for_parsing.py` — three `def test_*` at top level, sitting in
  a directory with a `conftest.py`, with a name matching neither `test_*.py`
  nor `*_test.py`, and no other module importing it. That is the seam.

## Must NOT be reported (3)

- `tests/checks/check_segfault.py` — Pillow's shape. It keeps ten hand-run
  scripts under `checks/` for segfault and large-memory reproductions, which
  are deliberately outside the suite. **The name is the author's mechanism**,
  exactly like the `check_*` methods in Pillow's `Tests/test_uploader.py`.
- `tests/benchmarks.py` — benchmarks are not tests. Pillow has one with 47
  `def test_*` in it.
- `tests/test_normal.py` — matches `test_*.py`, so it is collected.

## The duplicate bug this fixture also pins

`Tests/benchmarks.py` was reported **twice**, because nested test roots overlap:
both `Tests/` and an ancestor qualified as roots and each `rglob` found the same
file. Candidates are now deduplicated by resolved path.

## Added after FinancePy (a directory full of one convention is a harness)

- `tests/regressionish/TestThing1.py` through `TestThing6.py` must NOT be
  reported. FinancePy has **124** files named `TestFinXxx.py` under
  `tests/regression/`, which its own `.github/workflows/run-regression-tests.yml`
  drives via `scripts/run_all_regression_tests.py` and whose output it archives
  as `tests/regression/differences/*.testLog`. They sit under `testpaths`, so
  the directory is in scope, but the project runs them separately.

  **Many files in one directory sharing a non-matching name shape is a
  convention, not that many mistakes.** A genuine forgotten file is one or two
  among properly named siblings, which is why the threshold is five. Same
  counting insight as the vacuous scanner's three-reflexive-comparisons rule.
  `regression` also joined the named harness directories.

Expected total remains 1.
