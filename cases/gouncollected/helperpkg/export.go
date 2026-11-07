package helperpkg

import "testing"

// TestDirLockerUsage is an exported helper other packages' tests call.
func TestDirLockerUsage(t *testing.T, name string) {
	if name == "" {
		t.Fatal("empty")
	}
}
