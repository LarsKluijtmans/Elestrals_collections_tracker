// Rarity as *material*, never hue — element already owns hue, and two hue encodings in one
// dense row is unreadable (ux-guide §4).
//
// The label is always rendered: the material is redundant encoding, not the only one.
import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import {
  ELEMENT_HUES,
  RARITY_MATERIALS,
  hexToRgba,
  type ElementKey,
  type RarityKey,
} from "../theme/domain";

const SILVER = "linear-gradient(135deg,#C9D2E4,#8A97B4)";
const IRIDESCENT =
  "conic-gradient(from 180deg, #FF6A5A, #FFD84D, #4FDD9B, #5FDDEC, #B69BFF, #FF6A5A)";

export function RarityBadge({
  rarity,
  element,
}: {
  rarity: string;
  element?: string | null;
}) {
  const theme = useTheme();
  const entry = RARITY_MATERIALS[rarity as RarityKey];
  if (!entry) {
    // An unknown rarity is a catalog defect the importer rejects at the door, but a page
    // still has to render rather than crash on it.
    return <Box component="span" sx={{ fontSize: 12, color: "text.disabled" }}>{rarity}</Box>;
  }

  const { material, label } = entry;
  const base = {
    display: "inline-flex",
    alignItems: "center",
    borderRadius: 1,
    px: 1.25,
    py: 0.25,
    fontSize: 12,
    fontWeight: 600,
    lineHeight: 1.6,
    whiteSpace: "nowrap",
    position: "relative",
    overflow: "hidden",
  } as const;

  if (material.kind === "flat") {
    return (
      <Box component="span" sx={{ ...base, px: 0, color: material.tone === "muted" ? "text.disabled" : "text.secondary" }}>
        {label}
      </Box>
    );
  }

  if (material.kind === "ring") {
    return (
      <Box component="span" sx={{ ...base, color: "text.secondary", border: `1px solid ${theme.palette.divider}` }}>
        {label}
      </Box>
    );
  }

  if (material.kind === "dashed") {
    return (
      <Box component="span" sx={{ ...base, color: "text.secondary", border: `1px dashed ${theme.palette.divider}` }}>
        {label}
      </Box>
    );
  }

  if (material.kind === "element-gradient") {
    const hue = element && element in ELEMENT_HUES
      ? ELEMENT_HUES[element as ElementKey][theme.palette.mode === "dark" ? "dark" : "light"]
      : theme.palette.primary.main;
    return (
      <Box
        component="span"
        sx={{
          ...base,
          color: "text.primary",
          border: "1.5px solid transparent",
          backgroundImage: `linear-gradient(${theme.palette.background.paper}, ${theme.palette.background.paper}), linear-gradient(135deg, ${hue}, ${hexToRgba(hue, 0.35)})`,
          backgroundOrigin: "border-box",
          backgroundClip: "padding-box, border-box",
        }}
      >
        {label}
      </Box>
    );
  }

  if (material.kind === "iridescent") {
    return (
      <Box
        component="span"
        sx={{
          ...base,
          color: "text.primary",
          border: "1.5px solid transparent",
          backgroundImage: `linear-gradient(${theme.palette.background.paper}, ${theme.palette.background.paper}), ${IRIDESCENT}`,
          backgroundOrigin: "border-box",
          backgroundClip: "padding-box, border-box",
        }}
      >
        {label}
      </Box>
    );
  }

  // silver, with or without the 4s sheen sweep
  return (
    <Box
      component="span"
      sx={{
        ...base,
        color: "text.primary",
        border: "1px solid transparent",
        backgroundImage: `linear-gradient(${theme.palette.background.paper}, ${theme.palette.background.paper}), ${SILVER}`,
        backgroundOrigin: "border-box",
        backgroundClip: "padding-box, border-box",
        ...(material.sheen && {
          "&::after": {
            content: '""',
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(115deg, transparent 35%, rgba(255,255,255,0.55) 50%, transparent 65%)",
            transform: "translateX(-120%)",
            animation: "rarity-sheen 4s ease-in-out infinite",
          },
          "@keyframes rarity-sheen": {
            "0%, 60%": { transform: "translateX(-120%)" },
            "100%": { transform: "translateX(120%)" },
          },
          // Binding, not optional: ux-guide §9.
          "@media (prefers-reduced-motion: reduce)": {
            "&::after": { animation: "none", opacity: 0 },
          },
        }),
      }}
    >
      {label}
    </Box>
  );
}
