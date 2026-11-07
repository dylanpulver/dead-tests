package godead

import "testing"

func TestParse(t *testing.T) {
	v, err := parse("x")
	if err != nil {
		t.Fatalf("parse: %v", err)
		t.Log("never printed") // dead: Fatalf ends the goroutine
	}
	if v != 1 {
		t.Fatal("want 1")
	}
}

func TestSkipIsFine(t *testing.T) {
	t.Skip("disabled on purpose")
	t.Log("intentionally unreachable, not reported")
}

func parse(s string) (int, error) { return 1, nil }
