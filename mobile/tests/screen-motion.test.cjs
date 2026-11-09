const { test } = require("node:test");
const assert = require("node:assert/strict");
const {
  COMPACT_HEADER_HEIGHT,
  headerCollapseRange,
  shouldShowCompactHeader,
} = require("../src/lib/screen-motion.ts");

test("the regular header hands off before the first section passes under the toolbar", () => {
  assert.equal(COMPACT_HEADER_HEIGHT, 58);
  assert.deepEqual(headerCollapseRange(72), { start: 20, end: 48 });
  assert.equal(shouldShowCompactHeader(0, 72), false);
  assert.equal(shouldShowCompactHeader(33, 72), false);
  assert.equal(shouldShowCompactHeader(34, 72), true);
  assert.equal(shouldShowCompactHeader(1000, 72), true);
});

test("the taller Today header retains its title longer", () => {
  assert.deepEqual(headerCollapseRange(112), { start: 60, end: 88 });
  assert.equal(shouldShowCompactHeader(50, 112), false);
  assert.equal(shouldShowCompactHeader(88, 112), true);
});

test("returning to the top and elastic overscroll restore the expanded header", () => {
  for (const height of [0, 30, 72, 112, 180]) {
    assert.equal(shouldShowCompactHeader(500, height), true);
    assert.equal(shouldShowCompactHeader(0, height), false);
    assert.equal(shouldShowCompactHeader(-80, height), false);
    const { start, end } = headerCollapseRange(height);
    assert.ok(start >= 0);
    assert.ok(end > start);
  }
});

test("larger accessibility text moves the handoff instead of clipping the header", () => {
  const regular = headerCollapseRange(72);
  const largeText = headerCollapseRange(180);
  assert.equal(largeText.end - regular.end, 108);
  assert.equal(shouldShowCompactHeader(regular.end, 180), false);
});
