// Themes the WHOLE app from the project's branding — not just the login form.
//
// Two layers (ux-guide.md §2): chrome tokens come from branding-api and are tenant-
// overridable; element and rarity colours are constants in theme/domain.ts and are NOT.
//
// If branding-api is unreachable the built-in default palette renders and nothing else
// degrades — that is story 003's acceptance criterion, not a nicety.
import { createAuthClient } from "@lars-kluijtmans/react-auth";
import type { Branding } from "@lars-kluijtmans/react-auth";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { authConfig } from "../authConfig";
import { buildTheme, preferredMode } from "../theme/tokens";
import type { Mode } from "../theme/tokens";

type BrandingContextValue = {
  branding: Branding;
  loading: boolean;
  /** False when we fell back to the built-in palette. Surfaced so the UI can be honest. */
  brandingAvailable: boolean;
  mode: Mode;
  setMode: (m: Mode) => void;
};

const BrandingContext = createContext<BrandingContextValue>({
  branding: {},
  loading: true,
  brandingAvailable: false,
  mode: "dark",
  setMode: () => {},
});

export const useBranding = (): BrandingContextValue => useContext(BrandingContext);

export function BrandingThemeProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<Branding>({});
  const [loading, setLoading] = useState(true);
  const [brandingAvailable, setBrandingAvailable] = useState(false);
  const [mode, setMode] = useState<Mode>(preferredMode);

  useEffect(() => {
    let active = true;
    const client = createAuthClient({
      authApiUrl: authConfig.authApiUrl,
      clientId: authConfig.clientId,
      redirectUri: authConfig.redirectUri,
    });
    client
      .fetchBranding()
      .then((b) => {
        if (!active) return;
        setBranding(b);
        setBrandingAvailable(Object.keys(b ?? {}).length > 0);
      })
      .catch(() => {
        // Deliberately silent for the user: the app is fully usable on the default theme.
        if (active) setBrandingAvailable(false);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Follow the OS unless the user has chosen; an explicit choice wins in both directions.
  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = (e: MediaQueryListEvent) => setMode(e.matches ? "light" : "dark");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const theme = useMemo(() => buildTheme(branding, mode), [branding, mode]);

  return (
    <BrandingContext.Provider value={{ branding, loading, brandingAvailable, mode, setMode }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </BrandingContext.Provider>
  );
}
