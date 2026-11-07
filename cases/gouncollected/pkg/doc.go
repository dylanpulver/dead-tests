/*
Package pkg is documented the way rclone's fstest/run.go is, by showing a
test that a caller would write:

	func TestMkdir(t *testing.T) {
		r := NewRun(t)
		defer r.Finalise()
	}

A declaration inside a comment is not a declaration.
*/
package pkg

// NewRun is referenced by the doc comment above.
func NewRun(t any) any { return t }
