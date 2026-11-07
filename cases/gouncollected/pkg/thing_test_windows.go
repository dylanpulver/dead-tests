//go:build windows

package pkg

import "testing"

func TestWindowsOnlyBehaviour(t *testing.T) {
	if Parse("w") != "w" {
		t.Fatal("bad")
	}
}

func TestSharedName(t *testing.T) {
	if Parse("x") != "x" {
		t.Fatal("bad")
	}
}
