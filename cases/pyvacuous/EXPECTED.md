# _pyvacuous — expectations for find-vacuous-assertions.py

An assertion comparing a value to itself cannot fail. But three shapes LOOK
self-comparing and are real tests, and ibis-project/ibis produced 39 hits of
which 38 were these. Written after that triage.

## Must be reported (2)

- `test_real.py` -> `assertEqual(schedule.journal_entry, schedule.journal_entry)`
  erpnext's shape. An attribute compared to itself, inside a loop whose other
  lines compare DIFFERENT attributes against expected values. Nothing else in
  the function compares `schedule.journal_entry` to anything, which is what
  separates a mistake from a contract test.
- `test_real.py` -> `assertEqual(po.items[0].rate, po.items[0].rate)`
  erpnext's second. Subscript plus attribute, no call, no sibling comparison of
  that same expression.

## Must NOT be reported (5)

- `calls_on_both_sides`: `Scalar() == Scalar()` and
  `hash(Frozen(a=1)) == hash(Frozen(a=1))`. **Two separate evaluations**, so
  these test that independently constructed equal values compare and hash
  equal, which is exactly what a value type must guarantee. Twenty of ibis's
  thirty-nine were this, and the tool used to print them with a SIDE-EFFECT
  note, so it already knew and reported them anyway.
- `contract_matrix`: `ph1 == ph1` sitting among `ph1 != ph2`, `ph1 == ph4`.
  For a custom `__eq__`, reflexivity is not guaranteed and is a real property.
  ibis's `test_pseudo_hashable` asserts it across twelve lines.
- `loop_reflexivity`: `for obj in [a, b, c]: assert obj == obj`. The same
  contract written as a loop, which the matrix check cannot see because the
  siblings are compared under their own names. Keyed on the operand BEING the
  loop target, so an ATTRIBUTE of a loop variable is still reported.

## Added after zarr-python (`is` on an attribute is a caching test)

- `test_legit.py` -> `test_cached_property_identity`. zarr's
  `test_chunk_resolution` asserts `table.local is table.local` directly below
  `assert plan.partition() is partition`, which is the same check written with
  a call. Attribute access can run a property, so two accesses may return
  different objects, and asserting identity is the only way to pin that they do
  not. Restricted to `is` and to non-Name operands: erpnext's mistakes are
  `assertEqual`, so an `==` self-comparison on an attribute is still reported.

Expected total remains 2.

## Added after pydantic (three reflexive comparisons is a block)

- `test_legit.py` -> `test_three_reflexive_is_a_block`. pydantic's
  `test_validate_call` asserts `thing.a == thing.a`, `thing.c == thing.c` and
  `Thing.c == Thing.c` to check that `validate_call` wrappers compare equal
  across accesses, and a second cluster in the same file states the intent
  outright: `# verify that equality still holds for instance methods`.

  **Three or more in one function is a deliberate block, not three mistakes.**
  A real mistake comes alone, as erpnext's two do, one per test. Counting is
  what separates them, since neither the operator nor the operand shape does.

Expected total remains 2.

## Added after msgspec (a test named for comparison asserts reflexivity on purpose)

- `test_legit.py` -> `test_raw_comparison`. msgspec's real test of that name
  opens with `assert r == r` and `assert not r != r` before covering equal
  values, different values and memoryview slices. The counting rule misses it,
  because `!=` is excluded from the scan and `r` is never compared to anything
  else, so the function NAME is the only signal left.

  Safe because erpnext's real pair live in tests named
  `test_depreciation_schedule` and `test_blanket_order_rate`, which say nothing
  about comparison.

Expected total remains 2.
