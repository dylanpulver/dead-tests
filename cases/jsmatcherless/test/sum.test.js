const sum = (a, b) => a + b;

test('adds', () => {
  expect(sum(1, 2));            // dead: no matcher, verifies nothing
  expect(sum(2, 2)).toBe(4);    // fine
});

test('chain split across lines is fine', () => {
  expect(sum(1, 1))
    .toBe(2);
});

test('also dead', () => {
  const r = sum(5, 5);
  expect(r);
});
