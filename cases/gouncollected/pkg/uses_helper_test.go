package pkg

import (
	"testing"

	"fixture/helperpkg"
)

func TestUsesExportedHelper(t *testing.T) {
	helperpkg.TestDirLockerUsage(t, "n")
}
