# dead-tests

Find tests that look like coverage but can never fail, or never run at all.

A test with no `@Test` attribute compiles, sits in the suite and reads like a check. JUnit 5 never collects it. An `assert` after the raising call inside `pytest.raises` is never reached. A second `def test_area` silently replaces the first. `expect(x)` with no matcher verifies nothing. Every one of these stays green forever, and no runner or default linter says a word.

These scanners find them. Each one is a single stdlib-only file you can read in a sitting.

## Run it

With Docker, against the current directory:

```sh
docker run --rm -v "$PWD:/src" ghcr.io/dylanpulver/dead-tests
```

Or from a checkout, with Python 3.12+ (and Go, for the one Go check):

```sh
git clone https://github.com/dylanpulver/dead-tests
./dead-tests/deadtests scan path/to/repo
./dead-tests/deadtests run shadowed-tests path/to/repo
./dead-tests/deadtests list
```

`scan` detects the languages in the tree and runs every check that applies.

## Use in CI

On pull requests, this flags dead tests inline on the diff, only in the files the PR changes, so an old finding never lands on someone else's PR:

```yaml
on: pull_request

jobs:
  dead-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dylanpulver/dead-tests@v1
```

Inputs, all optional:

- `path`: directory to scan, default `.`
- `checks`: a subset to run, like `shadowed-tests, uncollected-java-tests`. Default is every check that applies.
- `changed-only`: report only files the PR changes, default `true`. Set it to `false` to report everything.
- `fail-on-findings`: fail the job when there is a finding, default `false`.
- `sarif-file`: also write every finding as SARIF to this path. See [SARIF](#sarif).

GitHub shows at most 10 warnings per step on the diff. The full list is in the job summary. The Go check needs Go on the runner, which GitHub's hosted runners have. Without it, that check is skipped with a notice.

## SARIF

`scan` and `run` take `--format sarif` and print SARIF 2.1.0 instead of text, with one rule per check. The text output goes to stderr so you still see it.

```sh
./dead-tests/deadtests scan --format sarif . > dead-tests.sarif
```

In the Action, set `sarif-file` and hand the file to GitHub code scanning. Then findings show up in the Security tab and on pull requests like any other code scanning alert. The SARIF file holds every finding, whatever `changed-only` says, because code scanning does its own diff filtering.

```yaml
permissions:
  contents: read
  security-events: write

steps:
  - uses: actions/checkout@v4
  - uses: dylanpulver/dead-tests@v1
    with:
      sarif-file: dead-tests.sarif
  - uses: github/codeql-action/upload-sarif@v4
    with:
      sarif_file: dead-tests.sarif
      category: dead-tests
```

## Checks

| Check | Language | Finds |
|---|---|---|
| `shadowed-tests` | Python | a later `def` with the same name, so pytest never runs the first |
| `uncollected-py-tests` | Python | asserting functions pytest never collects, by name |
| `uncollected-py-files` | Python | whole test files outside the `python_files` patterns |
| `dead-pytest-raises` | Python | asserts inside `pytest.raises` that provably cannot run |
| `dead-assertions` | Python | asserts after the raising call in `pytest.raises` (broader lead list) |
| `discarded-raises` | Python | `assertRaises`, `pytest.raises` and mock asserts that never execute |
| `swallowed-exceptions` | Python | tests that catch, pass and assert nothing |
| `vacuous-assertions` | Python | assertions comparing a value to itself |
| `missing-await` | Python | same-file coroutines called without `await` |
| `stale-version-gates` | Python | `skipif` gates true on every supported Python |
| `dead-version-shims` | Python | `sys.version_info` branches that cannot run |
| `uncollected-java-tests` | Java | `testFoo()` methods JUnit 5 cannot collect |
| `uncollected-kotlin-tests` | Kotlin | JUnit and kotlin.test functions missing `@Test` |
| `dead-junit4-expected` | Java | asserts made unreachable by `@Test(expected=...)` |
| `uncollected-dotnet-tests` | C# | NUnit and MSTest methods missing their attribute (xUnit warns on its own) |
| `uncollected-php-tests` | PHP | PHPUnit methods that are never collected |
| `dead-php-assertions` | PHP | PHPUnit asserts after a call that throws |
| `uncollected-ruby-tests` | Ruby | minitest methods that never run |
| `uncollected-go-tests` | Go | `Test` funcs `go test` never runs |
| `dead-go-statements` | Go | statements after `t.Fatal` or `t.FailNow` |
| `uncollected-rust-tests` | Rust | test-shaped fns with no `#[test]` |
| `matcherless-expects` | JS/TS | Jest and Vitest `expect(x)` with no matcher |

## Read every hit

These are lead generators, not oracles. A test with no attribute can be a deliberately parked case. A self-comparison can be a determinism test on a property that recomputes. Each scanner's docstring lists the false-positive shapes it has met in real code and which ones it filters, so read the file before trusting a result.

The other thing worth knowing: 2 of the first 11 dead tests I revived failed on their first run. A test that never ran was never kept up to date, so enabling it can surface a real bug or a stale expectation. Run the revived test before filing anything.

## Found with these

Merged fixes in projects other people depend on:

- [vuejs/core#16123](https://github.com/vuejs/core/pull/16123), two checks that never ran
- [laravel/framework#62312](https://github.com/laravel/framework/pull/62312), assertions that can never run
- [symfony/symfony#67854](https://github.com/symfony/symfony/pull/67854), dead assertions after the throwing call
- [pydantic#13921](https://github.com/pydantic/pydantic/pull/13921), [#14165](https://github.com/pydantic/pydantic/pull/14165) and [#14201](https://github.com/pydantic/pydantic/pull/14201), uncollected tests and dead `pytest.raises` tails
- [immer#1346](https://github.com/immerjs/immer/pull/1346), an `expect` with no matcher
- [PHP-Parser#1183](https://github.com/nikic/PHP-Parser/pull/1183), an assertion that never runs
- [Radarr#12075](https://github.com/Radarr/Radarr/pull/12075), three tests NUnit was never running
- [cakephp#19759](https://github.com/cakephp/cakephp/pull/19759), two methods PHPUnit never collected
- [Sylius#19267](https://github.com/Sylius/Sylius/pull/19267), a promotion total test that never ran
- [readthedocs.org#13345](https://github.com/readthedocs/readthedocs.org/pull/13345), shadowed duplicate test names
- [robolectric#11640](https://github.com/robolectric/robolectric/pull/11640), an unreachable assertion
- [statamic/cms#15758](https://github.com/statamic/cms/pull/15758), five tests missing their `Test` attribute
- [jackson-databind#6266](https://github.com/FasterXML/jackson-databind/pull/6266), 27 tests JUnit 5 did not collect
- [dnspython#1412](https://github.com/rthalley/dnspython/pull/1412), an unreachable assert
- [filesystem_spec#2192](https://github.com/fsspec/filesystem_spec/pull/2192), shadowed duplicate test names

## Tests

`cases/` holds a small positive case per check, most written before the scanner existed, plus negative controls. `tests/test_cases.py` runs every check on its case and compares the output to `tests/golden/`. A SARIF test checks `scan --format sarif` against the official 2.1.0 schema in `tests/`, and needs `pip install jsonschema`.

```sh
python -m unittest discover tests
```

## License

MIT
