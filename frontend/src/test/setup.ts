import "@testing-library/jest-dom/vitest";

// MUI's useMediaQuery calls matchMedia, which jsdom does not implement. Without this every
// component that reads a breakpoint throws before a single assertion runs.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
