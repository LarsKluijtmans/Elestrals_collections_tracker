/**
 * Chrome tokens — the tenant-overridable layer.
 *
 * These derive from branding-api's resolved theme. Element hues and rarity materials do NOT
 * live here; they are constants in `domain.ts`. Two layers, one hard rule between them: if a
 * tenant sets their primary to green, buttons go green — Wind stays Wind.
 *
 * See memory-bank/standards/ux-guide.md §2.
 */
import type { Branding } from '@lars-kluijtmans/react-auth';
import { createTheme } from '@mui/material';
import type { Theme } from '@mui/material';

export type Mode = 'light' | 'dark';

/** Built-in defaults. Rendered whenever branding-api is unreachable — the app must stay
 *  fully usable without it, so this is a real palette, not a placeholder. */
export const NEUTRALS = {
  dark: {
    bg0: '#0A0D16', bg1: '#111623', bg2: '#191F31', bg3: '#222A40',
    line: '#262E44', lineStrong: '#38425E',
    fg1: '#EAEEF9', fg2: '#A3AFC9', fg3: '#6C7896',
  },
  light: {
    bg0: '#F7F8FC', bg1: '#FFFFFF', bg2: '#F1F3F9', bg3: '#E7EAF3',
    line: '#E2E6F0', lineStrong: '#C7CEDF',
    fg1: '#131826', fg2: '#4A5570', fg3: '#737E99',
  },
} as const;

export const DEFAULT_BRAND = { dark: '#7B5CFF', light: '#6544E8' } as const;

export const SEMANTIC = {
  dark:  { success: '#35C77F', warning: '#F0B429', danger: '#F0524B', info: '#5AA0FF' },
  light: { success: '#0E7A50', warning: '#8A6100', danger: '#C0342E', info: '#1257C4' },
} as const;

const FONT_STACK = [
  'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif',
].join(',');

/** Pull the primary out of the resolved branding, falling back to our own. */
function brandPrimary(branding: Branding | undefined, mode: Mode): string {
  const colors = (branding as { colors?: Record<string, string> } | undefined)?.colors;
  return colors?.primary || DEFAULT_BRAND[mode];
}

export function buildTheme(branding: Branding | undefined, mode: Mode): Theme {
  const n = NEUTRALS[mode];
  const s = SEMANTIC[mode];
  const primary = brandPrimary(branding, mode);

  return createTheme({
    palette: {
      mode,
      primary: { main: primary },
      background: { default: n.bg0, paper: n.bg1 },
      text: { primary: n.fg1, secondary: n.fg2, disabled: n.fg3 },
      divider: n.line,
      success: { main: s.success },
      warning: { main: s.warning },
      error: { main: s.danger },
      info: { main: s.info },
    },
    shape: { borderRadius: 10 },
    // 4px base. Nothing off-scale.
    spacing: 4,
    typography: {
      fontFamily: FONT_STACK,
      // Every number is tabular. A column of prices that does not align cannot be read,
      // and this must never be unset downstream.
      allVariants: { fontVariantNumeric: 'tabular-nums' },
      h1: { fontWeight: 750, letterSpacing: '-0.025em', lineHeight: 1.15 },
      h2: { fontWeight: 750, letterSpacing: '-0.025em', lineHeight: 1.15 },
      h3: { fontWeight: 700, letterSpacing: '-0.02em' },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: { backgroundColor: n.bg0, color: n.fg1 },
          // Never remove a focus ring without replacing it.
          ':focus-visible': { outline: `2px solid ${primary}`, outlineOffset: 2 },
          '@media (prefers-reduced-motion: reduce)': {
            '*': { animationDuration: '0.01ms !important', transitionDuration: '0.01ms !important' },
          },
        },
      },
      MuiPaper: {
        // Elevation on dark is a surface step, not a shadow — big soft shadows read as mud
        // on a #0A0D16 ground.
        styleOverrides: {
          root: { backgroundImage: 'none', border: `1px solid ${n.line}` },
        },
      },
    },
  });
}

/** Respect the OS preference; an explicit in-app toggle can override this later. */
export function preferredMode(): Mode {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark';
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}
