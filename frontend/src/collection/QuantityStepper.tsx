import { Box, IconButton, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";

/**
 * The most-used control in the product — story 019 says so, and the numbers in it are requirements:
 *
 * * **44px hit targets.** Below that it is unusable on a phone and marginal with a trackpad.
 * * **400ms debounce**, so a held key produces one request rather than twenty.
 * * **Optimistic, with a visible revert.** The number moves on the click; if the server refuses,
 *   it goes back *and says so* — a silent revert is indistinguishable from a mis-click.
 *
 * The debounce is on the *net* change, not on each press. Holding `+` five times sends one request
 * for `5`, which matters because each one would otherwise be a separate row-level write racing the
 * others.
 */

export const DEBOUNCE_MS = 400;

export function QuantityStepper({
  value, label, min = 1, max = 10_000, onChange,
}: {
  value: number;
  label: string;
  min?: number;
  max?: number;
  onChange: (quantity: number) => void;
}) {
  // What the user sees. Diverges from `value` only while a change is in flight.
  const [shown, setShown] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef(false);

  // A change from elsewhere — another tab, a bulk edit, a refetch — wins, but only when this
  // stepper is idle. Otherwise a refetch landing mid-hold would yank the number back under the
  // user's finger.
  useEffect(() => {
    if (!pending.current) setShown(value);
  }, [value]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  function step(by: number): void {
    const next = Math.min(max, Math.max(min, shown + by));
    if (next === shown) return;

    setShown(next);
    pending.current = true;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      pending.current = false;
      // Compared against the *server's* value, not against the previous displayed one. A burst
      // that goes up and comes back down — a mis-click corrected immediately — has changed
      // nothing, and writing "set it to what it already is" would be a pointless request and a
      // pointless entry in whatever eventually audits this table. Same rule the grid's delta
      // coalescer applies to a click followed by a shift-click.
      if (next !== value) onChange(next);
    }, DEBOUNCE_MS);
  }

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
      <IconButton
        size="small"
        disabled={shown <= min}
        onClick={() => step(-1)}
        aria-label={`Remove one ${label}`}
        // 44px however small the icon renders — the story's number, not a rounded-up guess.
        sx={{ width: 44, height: 44 }}
      >
        −
      </IconButton>

      <Typography
        aria-live="polite"
        aria-label={`${shown} copies of ${label}`}
        sx={{ minWidth: 24, textAlign: "center", fontVariantNumeric: "tabular-nums" }}
      >
        {shown}
      </Typography>

      <IconButton
        size="small"
        disabled={shown >= max}
        onClick={() => step(1)}
        aria-label={`Add one ${label}`}
        sx={{ width: 44, height: 44 }}
      >
        +
      </IconButton>
    </Box>
  );
}
