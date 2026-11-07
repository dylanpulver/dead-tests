import unittest


def test_calls_on_both_sides():
    # Two separate evaluations: this is what a value type must guarantee.
    assert Scalar() == Scalar()
    assert hash(Frozen(a=1)) == hash(Frozen(a=1))


def test_contract_matrix():
    ph1, ph2, ph3, ph4 = make_four()
    # Reflexivity asserted alongside the non-reflexive cases.
    assert ph1 == ph1
    assert ph1 != ph2
    assert ph1 == ph3
    assert ph1 == ph4
    assert ph3 == ph3


def test_loop_reflexivity():
    a, b, c = make_three()
    for obj in [a, b, c]:
        assert obj == obj


class Scalar:
    def __eq__(self, other):
        return isinstance(other, Scalar)


class Frozen:
    def __init__(self, **kw):
        self.kw = kw

    def __hash__(self):
        return hash(tuple(sorted(self.kw.items())))


def make_four():
    return (1, 2, 3, 4)


def make_three():
    return (1, 2, 3)


def test_cached_property_identity():
    table = get_table()
    # zarr's shape: `is` on an attribute pins that the access is CACHED.
    # Attribute access can run a property, so two accesses may differ.
    assert table.local is table.local


def get_table():
    return None


def test_three_reflexive_is_a_block():
    thing, Thing = make_pair()
    # pydantic's shape: three reflexive comparisons in one function, checking
    # that validate_call wrappers compare equal across accesses. A real
    # mistake comes alone; a block of three is deliberate.
    assert thing.a == thing.a
    assert thing.c == thing.c
    assert Thing.c == Thing.c


def make_pair():
    return (None, None)


def test_raw_comparison():
    r = make_raw()
    # msgspec's shape: a test NAMED for comparison semantics, opening with
    # reflexivity before the interesting cases. The counting rule misses it
    # because != is excluded and r is never compared to anything else.
    assert r == r
    assert not r != r
    assert make_raw() == make_raw()


def make_raw():
    return 0
