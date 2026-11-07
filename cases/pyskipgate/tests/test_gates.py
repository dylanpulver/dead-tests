import sys

import pytest


@pytest.mark.skipif(sys.version_info >= (3, 10), reason="broken on new python")
def test_never_runs_lower_bound():
    assert True


@pytest.mark.skipif(sys.version_info < (3, 10), reason="needs 3.10")
def test_always_runs():
    assert True


@pytest.mark.skipif(sys.version_info < (3, 12), reason="needs 3.12")
def test_partially_skipped():
    assert True


@pytest.mark.skipif(sys.version_info >= (3, 15), reason="not yet supported")
def test_never_skipped_above_range():
    assert True


@pytest.mark.skipif(sys.platform == "win32", reason="posix only")
def test_platform_gate_not_a_version_gate():
    assert True


@pytest.mark.skip(reason="deliberately parked by a maintainer")
def test_unconditional_skip():
    assert True


@pytest.mark.skipif(sys.version_info[:2] != (3, 9), reason="3.9 only")
def test_never_runs_equality():
    assert True
