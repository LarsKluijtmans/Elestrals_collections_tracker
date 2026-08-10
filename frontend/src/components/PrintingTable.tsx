// Every printing of a card. The four encodings stay independent (ux-guide §4): element is a
// named hue chip, rarity is a material, and neither borrows the other's channel.
import {
  Box, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from "@mui/material";
import type { PrintingView } from "../api/backend";
import { ElementChip } from "./ElementChip";
import { RarityBadge } from "./RarityBadge";

const FINISH_LABELS: Record<string, string> = {
  normal: "Normal",
  foil: "Foil",
  reverse_foil: "Reverse foil",
  prismatic: "Prismatic",
};

const EDITION_LABELS: Record<string, string> = {
  first: "1st Edition",
  unlimited: "Unlimited",
};

export function PrintingTable({
  printings,
  element,
  onSelect,
}: {
  printings: PrintingView[];
  element?: string | null;
  /** Bolt 005 passes this to turn the table into an add-to-collection surface. */
  onSelect?: (printing: PrintingView) => void;
}) {
  if (printings.length === 0) {
    return (
      <Typography variant="body2" sx={{ color: "text.disabled" }}>
        No printings recorded.
      </Typography>
    );
  }

  return (
    <Table size="small" aria-label="Printings">
      <TableHead>
        <TableRow>
          <TableCell>Rarity</TableCell>
          <TableCell>Finish</TableCell>
          <TableCell>Edition</TableCell>
          <TableCell>Language</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {printings.map((printing) => (
          <TableRow
            key={printing.printing_id}
            hover={Boolean(onSelect)}
            onClick={onSelect ? () => onSelect(printing) : undefined}
            sx={onSelect ? { cursor: "pointer" } : undefined}
          >
            <TableCell>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <RarityBadge rarity={printing.rarity} element={element} />
                {element && <ElementChip element={element} size="xs" />}
              </Box>
            </TableCell>
            <TableCell sx={{ fontSize: 13 }}>
              {FINISH_LABELS[printing.finish] ?? printing.finish}
            </TableCell>
            <TableCell sx={{ fontSize: 13 }}>
              {EDITION_LABELS[printing.edition] ?? printing.edition}
            </TableCell>
            <TableCell sx={{ fontSize: 13, textTransform: "uppercase" }}>
              {printing.language}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
