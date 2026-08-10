import { AuthProvider } from "@lars-kluijtmans/react-auth";
import { BrowserRouter } from "react-router-dom";
import { authConfig } from "./authConfig";
import { BrandingThemeProvider } from "./branding/BrandingThemeProvider";
import { Gate } from "./components/Gate";

// Provider order: AuthProvider (session) → BrandingThemeProvider (theme from project
// branding) → BrowserRouter (deep links) → Gate (login form vs app shell).
//
// The router sits *inside* the auth provider on purpose. Login is embedded, so the URL never
// changes during sign-in — a deep link survives it without any return-path plumbing.
export function App() {
  return (
    <AuthProvider config={authConfig}>
      <BrandingThemeProvider>
        <BrowserRouter>
          <Gate />
        </BrowserRouter>
      </BrandingThemeProvider>
    </AuthProvider>
  );
}
