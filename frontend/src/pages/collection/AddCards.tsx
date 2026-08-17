import { Stack, Typography } from "@mui/material";
import { AddSearchBox } from "../../components/add/AddSearchBox";
import { CarriedDefaultsBar } from "../../components/add/CarriedDefaultsBar";
import { LiveAnnouncer } from "../../components/add/LiveAnnouncer";
import { SessionTally } from "../../components/add/SessionTally";

/**
 * `/collection/add` — keyboard-first single entry.
 *
 * The layout is deliberately thin. Every element that is not the search field is a distraction
 * from the one number this page is judged on: **median add under five seconds, 100 cards under
 * ten minutes**. If that target is missed, the bolt notes are explicit that the fix is the
 * interaction — fewer required fields, better defaults, more aggressive carry-forward — and not
 * optimising an API that already answers in 200ms. The bottleneck is decisions the user has to
 * make, not milliseconds.
 */
export function AddCardsPage() {
  return (
    <Stack sx={{ gap: 3, maxWidth: 1000 }}>
      <LiveAnnouncer />

      <Stack sx={{ gap: 0.5 }}>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>
          Add cards
        </Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          Type, arrow down, press Enter. Condition and finish carry forward.
          Ctrl+Z undoes the last add when the field is empty.
        </Typography>
      </Stack>

      <CarriedDefaultsBar />

      <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 3, alignItems: "flex-start" }}>
        <Stack sx={{ gap: 2, flex: 1, minWidth: 0 }}>
          <AddSearchBox />
        </Stack>
        <SessionTally />
      </Stack>
    </Stack>
  );
}
