// An integration test file: every fn here is a test unless it is a helper.

// HIT: no attribute, no args, asserts.
fn integration_forgotten() {
    assert_eq!(1 + 1, 2);
}

#[test]
fn integration_real() {
    assert_eq!(2 + 2, 4);
}

// NOT a hit: a helper called by the real test.
fn setup() -> i32 { 42 }

#[test]
fn integration_uses_setup() {
    assert_eq!(setup(), 42);
}
