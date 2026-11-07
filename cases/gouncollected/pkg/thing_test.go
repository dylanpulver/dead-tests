//go:build !windows

package pkg

import "testing"

func TestParsesInput(t *testing.T) {
	testSharedHelper(t, "a")
}

// Lowercase and nothing calls it: never collected.
func testParsesInput(t *testing.T) {
	if Parse("a") != "a" {
		t.Fatal("bad")
	}
}

// Lowercase but called by TestParsesInput: a deliberate shared helper.
func testSharedHelper(t *testing.T, in string) {
	if Parse(in) != in {
		t.Fatal("bad")
	}
}

// Declared here AND in thing_test_windows.go under the opposite constraint.
func TestSharedName(t *testing.T) {
	if Parse("x") != "x" {
		t.Fatal("bad")
	}
}
