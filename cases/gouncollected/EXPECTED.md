# _gouncollected — expectations, written before the fix

Fixture for `find-uncollected-go-tests.py`. `go test` collects a function only
when it is named `TestXxx` and lives in a file ending `_test.go`. Go rejects
unused variables and imports but never an unused function, so both mistakes
stay green forever.

`go list -f '{{.GoFiles}} {{.TestGoFiles}}'` is the ground truth, and it needs
no execution, so it works under any GOOS.

## Must be reported (3)

- `pkg/thing_test.go` -> `testParsesInput`
  Lowercase name in a real test file, takes *testing.T, nothing calls it.
- `pkg/thing_test_windows.go` -> `TestWindowsOnlyBehaviour`
  The GOOS suffix must come BEFORE `_test`, so this name does not end in
  `_test.go` and Go compiles it into the production package. caddy's
  `modules/logging/filewriter_test_windows.go` is exactly this.
- `pkg/thing_test_windows.go` -> `TestSharedName`
  **The case that exposed the bug.** A function of the same name is also
  declared in `thing_test.go` under the opposite build constraint. `repo_calls`
  subtracted a single declaration and read the second DECLARATION as a call, so
  this one was silently suppressed. In caddy that hid `TestFileCreationMode`,
  and only one of the file's two dead tests was reported. A declaration is not
  a call.

## Must NOT be reported (3)

- `pkg/thing_test.go` -> `testSharedHelper`, lowercase and called by a real
  test in the same package. Shared helpers are the dominant false positive.
- `pkg/thing_test.go` -> `TestParsesInput`, a correctly named, collected test.
- `helperpkg/export.go` -> `TestDirLockerUsage`, an exported TestXxx outside a
  `_test.go` file that another package's test calls on purpose. prometheus's
  `tsdbutil.TestDirLockerUsage` is the real instance.

## Added after rclone reported a doc comment as a declaration

- `pkg/doc.go` -> nothing. rclone's `fstest/run.go` opens with a package comment
  that DEMONSTRATES usage:

      /*
      func TestMkdir(t *testing.T) {
          r := fstest.NewRun(t)
      ...
      */

  and the exported-test pattern read that as a real declaration outside a
  `_test.go` file. Comment bodies are now blanked before matching, byte for
  byte so reported line numbers still point at real source. A doc comment is
  allowed to show a function; it is not declaring one.
