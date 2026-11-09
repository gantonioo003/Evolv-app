export const COMPACT_HEADER_HEIGHT = 58;
export const SCREEN_TOP_PADDING = 10;
export const SCREEN_SECTION_GAP = 24;

export function headerCollapseRange(headerHeight: number) {
  const end = Math.max(
    28,
    headerHeight +
      SCREEN_TOP_PADDING +
      SCREEN_SECTION_GAP -
      COMPACT_HEADER_HEIGHT,
  );
  return { start: Math.max(0, end - 28), end };
}

export function shouldShowCompactHeader(offset: number, headerHeight: number) {
  const { start, end } = headerCollapseRange(headerHeight);
  return offset >= (start + end) / 2;
}
