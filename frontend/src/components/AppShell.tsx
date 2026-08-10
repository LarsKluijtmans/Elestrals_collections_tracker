// The app shell: 240px left rail, 56px top bar, responsive collapse.
//   >= 1280px  full rail with labels
//   900–1279   64px icon rail
//   < 900px    bottom tab bar
// See memory-bank/standards/ux-guide.md §7.
import { useAuth, useUser } from "@lars-kluijtmans/react-auth";
import {
  AppBar, Avatar, Box, Button, Drawer, List, ListItemButton, ListItemIcon,
  ListItemText, Paper, Stack, Toolbar, Tooltip, Typography, useMediaQuery,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink, useLocation } from "react-router-dom";
import {
  Boxes, Heart, LayoutDashboard, Layers, Library, Settings, Upload,
} from "lucide-react";
import type { ReactNode } from "react";
import { useBranding } from "../branding/BrandingThemeProvider";
import { NAV_ROUTES } from "../routes";
import { LanguageSwitcher } from "./LanguageSwitcher";

const ICONS: Record<string, ReactNode> = {
  "/dashboard": <LayoutDashboard size={18} />,
  "/collection": <Library size={18} />,
  "/sets": <Layers size={18} />,
  "/sealed": <Boxes size={18} />,
  "/wishlist": <Heart size={18} />,
  "/import-export": <Upload size={18} />,
  "/settings/profile": <Settings size={18} />,
};

const RAIL_FULL = 240;
const RAIL_ICON = 64;

export function AppShell({ children }: { children: ReactNode }) {
  const theme = useTheme();
  // Active state comes from the router, not a prop — a prop drifts the moment a page
  // navigates without re-rendering the shell.
  const current = useLocation().pathname;
  const wide = useMediaQuery(theme.breakpoints.up("lg"));      // >= 1280
  const compact = useMediaQuery(theme.breakpoints.down("md")); // < 900
  const { logout } = useAuth();
  const { user } = useUser();
  const { brandingAvailable } = useBranding();

  const railWidth = wide ? RAIL_FULL : RAIL_ICON;

  const nav = (
    <List sx={{ py: 2 }}>
      {NAV_ROUTES.map((r) => {
        const active = current === r.path;
        const item = (
          <ListItemButton
            key={r.path}
            component={RouterLink}
            to={r.path}
            selected={active}
            sx={{
              mx: 2, borderRadius: 1.5, minHeight: 40,
              justifyContent: wide ? "flex-start" : "center",
              ...(active && { boxShadow: `inset 2px 0 0 ${theme.palette.primary.main}` }),
            }}
          >
            <ListItemIcon sx={{ minWidth: wide ? 32 : 0, color: "inherit" }}>
              {ICONS[r.path]}
            </ListItemIcon>
            {wide && <ListItemText primary={r.label} slotProps={{ primary: { sx: { fontSize: 14 } } }} />}
          </ListItemButton>
        );
        return wide ? item : <Tooltip key={r.path} title={r.label} placement="right">{item}</Tooltip>;
      })}
    </List>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      {!compact && (
        <Drawer
          variant="permanent"
          sx={{
            width: railWidth, flexShrink: 0,
            "& .MuiDrawer-paper": {
              width: railWidth, boxSizing: "border-box",
              bgcolor: "background.default", borderRight: `1px solid ${theme.palette.divider}`,
            },
          }}
        >
          <Toolbar sx={{ minHeight: 56, px: wide ? 4 : 0, justifyContent: wide ? "flex-start" : "center" }}>
            <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
              <Box sx={{
                width: 20, height: 20, borderRadius: 1.5,
                background: `linear-gradient(145deg, ${theme.palette.primary.main}, #B69BFF)`,
              }} />
              {wide && <Typography sx={{ fontWeight: 750, fontSize: 14 }}>Elestral Vault</Typography>}
            </Stack>
          </Toolbar>
          {nav}
        </Drawer>
      )}

      <Box sx={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <AppBar
          position="sticky"
          elevation={0}
          sx={{
            bgcolor: "background.paper",
            borderBottom: `1px solid ${theme.palette.divider}`,
            color: "text.primary",
          }}
        >
          <Toolbar sx={{ minHeight: 56, gap: 3 }}>
            <Box sx={{ flexGrow: 1 }} />
            {!brandingAvailable && (
              <Tooltip title="Branding service unreachable — using the default theme. Nothing else is affected.">
                <Typography variant="caption" color="text.disabled">default theme</Typography>
              </Tooltip>
            )}
            <LanguageSwitcher />
            <Tooltip title={user?.email ?? "Account"}>
              <Avatar sx={{ width: 28, height: 28, fontSize: 13 }}>
                {(user?.email ?? "?").slice(0, 1).toUpperCase()}
              </Avatar>
            </Tooltip>
            <Button size="small" onClick={logout}>Sign out</Button>
          </Toolbar>
        </AppBar>

        <Box component="main" sx={{ flexGrow: 1, p: 6, maxWidth: 1440, width: "100%", mx: "auto" }}>
          {children}
        </Box>

        {compact && (
          <Paper
            square
            elevation={0}
            sx={{ position: "sticky", bottom: 0, borderTop: `1px solid ${theme.palette.divider}` }}
          >
            <Stack direction="row" sx={{ justifyContent: "space-around", py: 1 }}>
              {NAV_ROUTES.slice(0, 5).map((r) => (
                <Tooltip key={r.path} title={r.label}>
                  <ListItemButton
                    component={RouterLink}
                    to={r.path}
                    selected={current === r.path}
                    sx={{ flexDirection: "column", borderRadius: 1.5, minWidth: 56, py: 1 }}
                  >
                    <ListItemIcon sx={{ minWidth: 0, color: "inherit" }}>{ICONS[r.path]}</ListItemIcon>
                  </ListItemButton>
                </Tooltip>
              ))}
            </Stack>
          </Paper>
        )}
      </Box>
    </Box>
  );
}
