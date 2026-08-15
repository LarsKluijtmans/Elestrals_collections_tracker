// An element chip: tinted background, full-strength text and border — and always the name.
//
// ux-guide §9: colour is never the only encoding. Roughly 1 in 12 men has a red-green
// deficiency, and Fire/Wind would be indistinguishable on hue alone.
import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import {
  ELEMENT_BORDER_ALPHA,
  ELEMENT_CHIP_ALPHA,
  ELEMENT_HUES,
  hexToRgba,
  type ElementKey,
} from "../theme/domain";

export function ElementChip({ element, size = "sm" }: { element: string | null; size?: "sm" | "xs" }) {
  const theme = useTheme();
  if (!element || !(element in ELEMENT_HUES)) return null;

  const hue = ELEMENT_HUES[element as ElementKey];
  // Dark-first product; the light values are darkened for AA on white.
  const colour = theme.palette.mode === "dark" ? hue.dark : hue.light;

  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: 1,
        px: size === "xs" ? 1 : 1.5,
        py: 0.25,
        fontSize: size === "xs" ? 11 : 12,
        fontWeight: 600,
        lineHeight: 1.6,
        whiteSpace: "nowrap",
        color: colour,
        // Never a solid fill — solid saturation belongs to the brand accent alone, which is
        // also what keeps Lunar from competing with a violet brand primary.
        backgroundColor: hexToRgba(colour, ELEMENT_CHIP_ALPHA),
        border: `1px solid ${hexToRgba(colour, ELEMENT_BORDER_ALPHA)}`,
      }}
    >
      {hue.label}
    </Box>
  );
}
