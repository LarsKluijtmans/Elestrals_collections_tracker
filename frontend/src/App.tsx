import { AuthProvider } from "@lars-kluijtmans/react-auth";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { authConfig } from "./authConfig";
import { BrandingThemeProvider } from "./branding/BrandingThemeProvider";
import { Gate } from "./components/Gate";

// Provider order: AuthProvider (session) → BrandingThemeProvider (theme from project
// branding) → QueryClientProvider (server state) → BrowserRouter (deep links) → Gate.
//
// The router sits *inside* the auth provider on purpose. Login is embedded, so the URL never
// changes during sign-in — a deep link survives it without any return-path plumbing.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The catalog is read-mostly and served with a five-minute cache header; refetching it
      // on every window focus would be churn for data that does not move.
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 60_000,
    },
  },
});

export function App() {
  return (
    <AuthProvider config={authConfig}>
      <BrandingThemeProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Gate />
          </BrowserRouter>
        </QueryClientProvider>
      </BrandingThemeProvider>
    </AuthProvider>
  );
}
