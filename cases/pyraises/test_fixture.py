import pytest


def test_dead_tail_assert():
    with pytest.raises(ValueError):
        parse("nope")
        assert parse("ok") == 1


def test_dead_tail_helper():
    with pytest.raises(KeyError):
        lookup("missing")
        assert_frame_equal(lookup("a"), 1)


def test_dead_middle_assert():
    with pytest.raises(TypeError):
        coerce(None)
        assert coerce(1) == 1
        cleanup()


def test_assert_is_the_raiser():
    with pytest.raises(AssertionError):
        assert False


def test_expects_assertion_error():
    with pytest.raises(AssertionError):
        setup()
        assert thing() == 2


def test_expects_bare_exception():
    with pytest.raises(Exception):
        boom()
        assert after() == 3


def test_warns_not_raises():
    with pytest.warns(DeprecationWarning):
        old_api()
        assert new_api() == 4


def test_assert_before_raiser():
    with pytest.raises(ValueError):
        assert precondition() is True
        boom()


def test_unresolvable_exc():
    exc = pick_exception()
    with pytest.raises(exc):
        boom()
        assert after() == 5


def test_fail_inside_block_is_a_diagnostic():
    # pymc and dash both use this: the fail() is REACHED when parse does not
    # raise, and Failed is not ValueError, so it propagates and names the case.
    # Deliberate, not dead. MUST NOT be a hit.
    with pytest.raises(ValueError):
        parse("nope")
        pytest.fail("parse('nope') should have raised")


def test_bare_fail_inside_block():
    # Same idiom with an unqualified fail(). MUST NOT be a hit.
    with pytest.raises(KeyError):
        lookup("missing")
        fail("lookup should have raised")


@pytest.mark.xfail(reason="see issue #334", strict=True)
def test_xfail_reproduction():
    # fsspec's shape: the whole test documents a known bug, so its own failure
    # is the point and the reachability of this assertion is not a defect.
    with pytest.raises(IsADirectoryError):
        of = open_files("zip://*.txt::simplecache::file:///tmp/f1.zip")
        assert len(of) == 2
