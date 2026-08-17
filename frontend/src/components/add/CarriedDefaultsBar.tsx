import { MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useEffect } from "react";
import { useAddSession } from "../../session/AddSessionContext";
import type { Condition } from "../../session/types";

const CONDITIONS: Condition[] = [
  "mint", "near_mint", "lightly_played", "moderately_played", "heavily_played", "damaged",
];
const FINISHES = ["normal", "foil", "reverse_foil", "prismatic"];

/**
 * Condition and finish, carried between adds.
 *
 * This bar is the single largest contributor to the five-second target, and it works by being
 * *ignorable*: a collector emptying a uniform box sets it once and never looks at it again. The
 * settings survive every add and every failure, and reset only on leaving the session.
 *
 * `Alt+C` and `Alt+F` change them without leaving the keyboard, because the whole flow is
 * keyboard-only and a picker that needs a mouse would break it for exactly the user who is
 * entering two hundred cards.
 */
export function CarriedDefaultsBar() {
  const { carried, changeDefaults } = useAddSession();

  useEffect(() => {
    function onKey(event: KeyboardEvent): void {
      if (!event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "c") {
        event.preventDefault();
        changeDefaults({ condition: cycle(CONDITIONS, carried.condition) });
      } else if (key === "f") {
        event.preventDefault();
        changeDefaults({ finish: cycle(FINISHES, carried.finish) });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [carried.condition, carried.finish, changeDefaults]);

  return (
    <Stack direction="row" sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}>
      <TextField
        select
        size="small"
        label="Condition"
        value={carried.condition}
        onChange={(event) => changeDefaults({ condition: event.target.value as Condition })}
        sx={{ minWidth: 180 }}
        helperText="Alt+C"
      >
        {CONDITIONS.map((condition) => (
          <MenuItem key={condition} value={condition}>
            {condition.replace(/_/g, " ")}
          </MenuItem>
        ))}
      </TextField>

      <TextField
        select
        size="small"
        label="Finish"
        value={carried.finish}
        onChange={(event) => changeDefaults({ finish: event.target.value })}
        sx={{ minWidth: 160 }}
        helperText="Alt+F"
      >
        {FINISHES.map((finish) => (
          <MenuItem key={finish} value={finish}>
            {finish.replace(/_/g, " ")}
          </MenuItem>
        ))}
      </TextField>

      <Typography sx={{ fontSize: 12, color: "text.disabled", maxWidth: 320 }}>
        These carry forward to every add until you change them.
      </Typography>
    </Stack>
  );
}

function cycle<T>(options: T[], current: T): T {
  const index = options.indexOf(current);
  return options[(index + 1) % options.length];
}
