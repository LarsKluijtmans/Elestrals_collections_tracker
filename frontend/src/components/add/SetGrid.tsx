import { Badge, Box, Card, CardActionArea, Stack, Typography } from "@mui/material";
import { useEffect, useMemo, useRef } from "react";
import type { SetChecklistEntry } from "../../api/backend";
import { useAddSession } from "../../session/AddSessionContext";
import { createCoalescer } from "../../session/deltaCoalescer";

/**
 * A whole set as clickable tiles — story 017.
 *
 * Click is +1, shift-click is −1. Two rules from the story are structural rather than cosmetic:
 *
 * **Tiles reserve their aspect ratio before the art loads.** The story puts it plainly: a grid
 * that jumps while you are clicking it is a grid that records the wrong card. `aspectRatio` on the
 * image box means the layout is final before any image arrives.
 *
 * **Rapid clicks on one tile coalesce.** Not only into one request — into **one undo entry**.
 * Three clicks in 300ms is one record of +3, or the undo stack becomes a keystroke log and a
 * collector who mis-clicked four times has to press undo four times.
 *
 * Badges read the session's own view of the quantity, so a tile updates on click rather than on
 * response. That is the same optimism the tally uses, for the same reason.
 */
export function SetGrid({ entries }: { entries: SetChecklistEntry[] }) {
  const { add, quantityFor } = useAddSession();

  // One coalescer for the whole grid, per printing inside it. Recreated only if `add` changes.
  const coalescer = useMemo(
    () =>
      createCoalescer((printingId, delta) => {
        const entry = entries.find((e) =>
          e.printings.some((p) => p.printing_id === printingId),
        );
        const printing = entry?.printings.find((p) => p.printing_id === printingId);
        if (!entry || !printing) return;
        void add({
          printingId,
          delta,
          label: {
            name: entry.name,
            setCode: entry.collector_number.split("-")[0] ?? "",
            collectorNumber: entry.collector_number,
            finish: printing.finish,
          },
        });
      }),
    [add, entries],
  );

  const coalescerRef = useRef(coalescer);
  coalescerRef.current = coalescer;

  // Anything still pending when the page unmounts is sent, not dropped. Navigating away mid-burst
  // must not lose the clicks a collector already made.
  useEffect(() => () => coalescerRef.current.flushAll(), []);

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
        gap: 1.5,
      }}
    >
      {entries.map((entry) => {
        const printing = entry.printings[0];
        if (!printing) return null;
        const owned = quantityFor(printing.printing_id);

        return (
          <Card key={entry.card_id} variant="outlined">
            <CardActionArea
              onClick={(event) =>
                // Shift-click at zero is a no-op with no error flash — the user was aiming at a
                // different tile, and a red banner for a missed click is noise.
                coalescer.push(printing.printing_id, event.shiftKey ? -1 : 1)
              }
              aria-label={`${entry.name}. ${owned ?? 0} owned. Click to add, shift-click to remove.`}
            >
              <Badge
                badgeContent={owned ?? 0}
                color={owned ? "primary" : "default"}
                sx={{ width: "100%" }}
              >
                <Stack sx={{ width: "100%" }}>
                  <Box
                    sx={{
                      // Reserved BEFORE the image loads. The grid must not reflow under a
                      // clicking finger.
                      aspectRatio: "5 / 7",
                      width: "100%",
                      bgcolor: "action.hover",
                      backgroundImage: printing.image_url
                        ? `url(${printing.image_url})`
                        : undefined,
                      backgroundSize: "cover",
                      backgroundPosition: "center",
                    }}
                    role="img"
                    aria-label={printing.alt_text}
                  />
                  <Typography sx={{ fontSize: 12, p: 0.75 }} noWrap>
                    {entry.collector_number} · {entry.name}
                  </Typography>
                </Stack>
              </Badge>
            </CardActionArea>
          </Card>
        );
      })}
    </Box>
  );
}
