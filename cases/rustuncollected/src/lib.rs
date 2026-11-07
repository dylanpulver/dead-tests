pub fn add(a: i32, b: i32) -> i32 { a + b }

#[cfg(test)]
mod tests {
    use super::*;

    // HIT: looks exactly like its neighbours and carries no attribute.
    fn forgotten_check() {
        assert_eq!(add(1, 2), 3);
    }

    #[test]
    fn real_check() {
        assert_eq!(add(2, 2), 4);
    }

    // NOT a hit: takes arguments, so it is a helper.
    fn helper(a: i32) -> i32 { a * 2 }

    #[test]
    fn uses_helper() {
        assert_eq!(helper(2), 4);
    }

    // NOT a hit: called by another test, so it is a shared body.
    fn shared_body() {
        assert!(true);
    }

    #[test]
    fn calls_shared() {
        shared_body();
    }

    // NOT a hit: #[ignore] is the author saying "deliberate".
    #[test]
    #[ignore]
    fn skipped_on_purpose() {
        assert!(false);
    }

    // NOT a hit: a non-std test attribute still collects.
    #[tokio::test]
    async fn async_check() {
        assert!(true);
    }

    // NOT a hit: returns a value, so it is a fixture/builder.
    fn make_thing() -> Vec<i32> { vec![1, 2, 3] }

    #[test]
    fn uses_make_thing() {
        assert_eq!(make_thing().len(), 3);
    }
}

// NOT a hit: outside any cfg(test) module, this is production code.
fn internal_helper() {
    let _ = add(1, 1);
}
