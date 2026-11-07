import pytest


def test_swallow_whole_body():
    try:
        parse("nope")
    except ValueError:
        pass


def test_swallow_no_fail():
    db = make_db()
    try:
        db.insert(bad_row)
    except KeyError:
        pass


def test_swallow_broad():
    try:
        risky()
    except Exception:
        pass


def test_has_fail_after_call():
    try:
        parse("nope")
        pytest.fail("should have raised")
    except ValueError:
        pass


def test_asserts_after_try():
    db = make_db()
    try:
        db.insert(bad_row)
    except KeyError:
        pass
    assert db.count() == 0


def test_asserts_inside_handler():
    try:
        parse("nope")
    except ValueError as e:
        assert "bad input" in str(e)


def test_optional_import():
    try:
        import fancy
    except ImportError:
        pass
    assert baseline() == 1


def test_cleanup_suppressed():
    path = write_temp()
    assert path.exists()
    try:
        path.unlink()
    except OSError:
        pass


def test_uses_pytest_raises():
    with pytest.raises(ValueError):
        parse("nope")


def test_raises_assertion_with_cleanup_suppressed():
    # The nltk shape: real assertions are pytest.raises blocks, and the only
    # try/except pass is cleanup in a finally. MUST NOT be a hit.
    tmp = make_tmp()
    try:
        with pytest.raises(PermissionError):
            pathsec.open(str(tmp), "rb")
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def test_invalid_input_rejected_via_raises():
    # Name claims a rejection AND asserts via pytest.raises. MUST NOT be a hit.
    try:
        with pytest.raises(ValueError):
            parse("bad")
    except OSError:
        pass


def test_invalid_key_rejected_via_else_raise():
    # The canonical pre-pytest idiom: the `else` branch IS the fail mechanism.
    # petl and tenacity both use exactly this. MUST NOT be a hit.
    o = make_record()
    try:
        o['baz']
    except KeyError:
        pass
    else:
        raise Exception('expected exception not raised')


def test_bad_input_rejected_via_else_fail():
    # Same idiom with a fail() call instead of a raise. MUST NOT be a hit.
    try:
        parse("bad")
    except ValueError:
        pass
    else:
        pytest.fail("expected exception not raised")
